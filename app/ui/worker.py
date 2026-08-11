"""队列工作线程：所有耗时操作在此线程运行，通过 Signal 通知 UI。"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config import Config
from app.core.pipeline import Pipeline, PipelineError
from app.models import FileJob, FileStatus
from app.providers.base import create_provider


class QueueSignals(QObject):
    """Signal 容器（必须挂 QObject 下）。"""

    log = Signal(str, str)  # level("info"/"error"/"warn"), message
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
        total = len(self._jobs)
        done = 0

        for idx, job in enumerate(self._jobs):
            if self._stop.is_set():
                job.status = FileStatus.CANCELED
                self.signals.file_done.emit(idx, "canceled", "用户停止")
                break

            job.status = FileStatus.PROCESSING
            self.signals.file_started.emit(idx)

            try:
                out = pipeline.process_file(
                    job,
                    progress=lambda pct, i=idx: self.signals.file_progress.emit(i, pct),
                    log=lambda lvl, msg: self.signals.log.emit(lvl, msg),
                    stop=self._stop,
                )
                job.status = FileStatus.SUCCESS
                self.signals.file_done.emit(idx, "success", str(out))
            except PipelineError as e:
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

        self.signals.queue_finished.emit()

    @Slot()
    def stop(self) -> None:
        """请求停止（跨线程自动排队调用）。"""
        self._stop.set()
