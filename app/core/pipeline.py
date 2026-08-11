"""单文件处理管线：转码 → 切块 → 识别 → 生成 SRT → 写盘。"""
from __future__ import annotations

import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Callable

from app.config import Config
from app.core.audio_chunker import Chunk, split_wav
from app.core.audio_util import transcode_to_wav
from app.core.srt_builder import segments_to_srt
from app.core.wav_util import read_wav_duration_ms
from app.models import FileJob, Segment
from app.providers.base import ASRProvider


class PipelineError(Exception):
    """处理失败（日志由 worker 记录，继续下一个文件）。"""


class Pipeline:
    def __init__(self, cfg: Config, provider: ASRProvider):
        self.cfg = cfg
        self.provider = provider

    def process_file(
        self,
        job: FileJob,
        progress: Callable[[int], None],
        log: Callable[[str, str], None],
        stop: threading.Event,
    ) -> Path:
        """执行单文件转换，返回输出的 .srt 路径。"""
        tmp_root = Path(tempfile.gettempdir()) / f"Scrybe_{uuid.uuid4().hex}"
        wav = tmp_root / "audio.wav"
        try:
            tmp_root.mkdir(parents=True, exist_ok=True)

            # 1. 转码
            log("info", f"[{job.source.name}] 正在提取音频…")
            transcode_to_wav(job.source, wav)
            progress(8)

            # 2. 判断是否需要切块
            size = wav.stat().st_size
            cap = self.provider.capability().max_file_size_bytes
            if cap is not None and size > cap:
                log("info", f"[{job.source.name}] 音频 {size // 1024 // 1024}MB 超过限制，自动切块")
                chunks = split_wav(wav, self.cfg.chunk_seconds, tmp_root / "chunks")
            else:
                dur = read_wav_duration_ms(wav)
                chunks = [Chunk(index=0, path=wav, start_ms=0, end_ms=dur)]
            progress(12)

            # 3. 逐块识别 + 偏移合并
            all_segments: list[Segment] = []
            total = len(chunks)
            for i, ch in enumerate(chunks):
                if stop.is_set():
                    raise PipelineError("已停止")
                if total > 1:
                    log("info", f"[{job.source.name}] 识别第 {i + 1}/{total} 段…")
                res = self.provider.transcribe_wav(
                    ch.path, self.cfg.language,
                    log=lambda m: log("info", m),
                    stop=stop,
                )
                for seg in res.segments:
                    seg.start_ms += ch.start_ms
                    seg.end_ms += ch.start_ms
                    all_segments.append(seg)
                progress(12 + round((i + 1) / total * 78))

            # 4. 生成 SRT
            srt_text = segments_to_srt(all_segments, merge_gap_ms=self.cfg.merge_gap_ms)
            out_path = job.output_dir / f"{job.source.stem}.srt"
            job.output_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(srt_text, encoding="utf-8-sig")
            progress(100)
            log("info", f"[{job.source.name}] 完成 → {out_path}")
            return out_path

        except Exception as e:
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(str(e)) from e
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
