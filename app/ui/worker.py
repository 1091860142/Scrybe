"""队列工作线程：音频提取并行、API 识别串行；所有耗时操作在此线程运行，通过 Signal 通知 UI。"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config import Config
from app.core.pipeline import Pipeline, PipelineError
from app.models import FileJob, FileStatus
from app.providers.base import create_provider


class QueueSignals(QObject):
    """Signal 容器（必须挂 QObject 下）。"""

    log = Signal(str, str)  # level("info"/"error"/"warn"), message
    queue_phase = Signal(str)  # "extract"(提取) | "recognize"(识别)
    file_started = Signal(int)  # job_index
    file_progress = Signal(int, int)  # job_index, percent 0-100
    file_done = Signal(int, str, str)  # job_index, "success"|"failed"|"canceled", detail
    queue_progress = Signal(int, int)  # done_count, total_count
    queue_finished = Signal()


class QueueWorker(QObject):
    def __init__(self, jobs: list[FileJob], cfg: Config):
        super().__init__()
        self._jobs = jobs
        self._cfg = cfg
        self._stop = threading.Event()
        self.signals = QueueSignals()

    @Slot()
    def run(self) -> None:
        provider = create_provider(self._cfg)
        pipeline = Pipeline(self._cfg, provider)

        pending = [(idx, j) for idx, j in enumerate(self._jobs) if j.status != FileStatus.SUCCESS]
        if not pending:
            self.signals.queue_finished.emit()
            return
        total = len(pending)
        wav_of: dict[int, Path] = {}  # job_index -> wav
        failed: dict[int, str] = {}  # job_index -> error

        # ---- 阶段1：并行提取音频 ----
        self.signals.queue_phase.emit("extract")
        self._extract_parallel(pipeline, pending, wav_of, failed, total)

        # ---- 阶段2：串行识别（按队列顺序，一个返回后识别下一个） ----
        self.signals.queue_phase.emit("recognize")
        done = 0
        for idx, job in enumerate(self._jobs):
            if job.status == FileStatus.SUCCESS:
                continue
            if self._stop.is_set():
                break

            wav = wav_of.get(idx)
            if wav is None:
                # 提取阶段失败或未完成
                job.status = FileStatus.FAILED
                job.error = failed.get(idx, "音频提取未完成")
                self.signals.file_done.emit(idx, "failed", job.error)
                done += 1
                self.signals.queue_progress.emit(done, total)
                continue

            job.status = FileStatus.PROCESSING
            self.signals.file_started.emit(idx)

            try:
                out = pipeline.recognize(
                    job, wav,
                    progress=lambda pct, i=idx: self.signals.file_progress.emit(i, pct),
                    log=lambda lvl, msg: self.signals.log.emit(lvl, msg),
                    stop=self._stop,
                )
                job.status = FileStatus.SUCCESS
                self.signals.file_done.emit(idx, "success", str(out))
            except PipelineError as e:
                if self._stop.is_set():
                    job.status = FileStatus.CANCELED
                    job.error = "用户停止"
                    self.signals.file_done.emit(idx, "canceled", "用户停止")
                else:
                    job.status = FileStatus.FAILED
                    job.error = str(e)
                    self.signals.file_done.emit(idx, "failed", str(e))
                    self.signals.log.emit("error", f"{job.source.name}: {e}")
            except Exception as e:
                job.status = FileStatus.FAILED
                job.error = str(e)
                self.signals.file_done.emit(idx, "failed", str(e))
                self.signals.log.emit("error", f"{job.source.name}: {e}")

            done += 1
            self.signals.queue_progress.emit(done, total)

        # 停止时：剩余未处理任务标记为已取消
        if self._stop.is_set():
            for idx, job in enumerate(self._jobs):
                if job.status not in (FileStatus.SUCCESS, FileStatus.CANCELED, FileStatus.FAILED):
                    job.status = FileStatus.CANCELED
                    job.error = "用户停止"
                    self.signals.file_done.emit(idx, "canceled", "用户停止")

        self.signals.queue_finished.emit()

    # ---- 阶段1：并行提取 ----
    def _extract_parallel(
        self,
        pipeline: Pipeline,
        pending: list[tuple[int, FileJob]],
        wav_of: dict[int, Path],
        failed: dict[int, str],
        total: int,
    ) -> None:
        n = max(1, self._cfg.parallel_extractions)
        done = 0
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures: dict = {}
            for idx, job in pending:
                if self._stop.is_set():
                    break
                futures[pool.submit(self._extract_one, pipeline, job)] = idx

            for fut in as_completed(futures):
                idx = futures[fut]
                done += 1
                self.signals.queue_progress.emit(done, total)
                if self._stop.is_set():
                    continue  # 结果不收集，剩余任务由 run() 统一标记取消
                try:
                    wav_of[idx] = fut.result()
                except PipelineError as e:
                    failed[idx] = str(e)
                    self.signals.log.emit("error", f"{self._jobs[idx].source.name}: {e}")
                except Exception as e:
                    failed[idx] = str(e)
                    self.signals.log.emit("error", f"{self._jobs[idx].source.name}: {e}")

    def _extract_one(self, pipeline: Pipeline, job: FileJob) -> Path:
        return pipeline.extract(job, log=self._emit_log)

    def _emit_log(self, level: str, msg: str) -> None:
        self.signals.log.emit(level, msg)

    @Slot()
    def stop(self) -> None:
        """请求停止（跨线程自动排队调用）。"""
        self._stop.set()
