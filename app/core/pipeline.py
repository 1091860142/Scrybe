"""单文件处理管线：提取（可并行）→ 切块 → 识别（串行）→ 生成 SRT → 写盘。

提取阶段产生的 WAV 缓存在系统临时目录，识别失败重试时可直接复用，无需重新提取。
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import threading
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


def cache_dir() -> Path:
    """提取的 WAV 缓存目录（重试时跳过重复提取）。"""
    return Path(tempfile.gettempdir()) / "Scrybe_cache"


def _cache_path(source: Path) -> Path:
    key = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:16]
    return cache_dir() / f"{key}.wav"


class Pipeline:
    def __init__(self, cfg: Config, provider: ASRProvider):
        self.cfg = cfg
        self.provider = provider

    def extract(self, job: FileJob, log: Callable[[str, str], None]) -> Path:
        """提取音频到缓存并返回 WAV 路径；已缓存则直接复用。失败抛 PipelineError。"""
        wav = _cache_path(job.source)
        if wav.exists() and wav.stat().st_size > 0:
            log("info", f"[{job.source.name}] 音频已缓存，跳过提取")
            return wav
        log("info", f"[{job.source.name}] 正在提取音频…")
        cache_dir().mkdir(parents=True, exist_ok=True)
        tmp = wav.with_suffix(".tmp")
        try:
            transcode_to_wav(job.source, tmp)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(str(e)) from e
        tmp.replace(wav)
        return wav

    def recognize(
        self,
        job: FileJob,
        wav: Path,
        progress: Callable[[int], None],
        log: Callable[[str, str], None],
        stop: threading.Event,
    ) -> Path:
        """切块并逐块识别（串行，按队列顺序），生成 SRT 写盘，返回输出路径。"""
        chunk_root = Path(tempfile.mkdtemp(prefix="Scrybe_chunks_"))
        try:
            # 1. 判断是否需要切块
            size = wav.stat().st_size
            cap = self.provider.capability().max_file_size_bytes
            if cap is not None and size > cap:
                log("info", f"[{job.source.name}] 音频 {size // 1024 // 1024}MB 超过限制，自动切块")
                chunks = split_wav(wav, self.cfg.chunk_seconds, chunk_root)
            else:
                dur = read_wav_duration_ms(wav)
                chunks = [Chunk(index=0, path=wav, start_ms=0, end_ms=dur)]
            progress(5)

            # 2. 逐块识别 + 偏移合并
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
                progress(5 + round((i + 1) / total * 90))

            # 3. 生成 SRT
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
            shutil.rmtree(chunk_root, ignore_errors=True)

    def process_file(
        self,
        job: FileJob,
        progress: Callable[[int], None],
        log: Callable[[str, str], None],
        stop: threading.Event,
    ) -> Path:
        """单文件完整处理（提取 + 识别）。供单文件调用与离线测试使用。"""
        wav = self.extract(job, log)
        return self.recognize(job, wav, progress, log, stop)
