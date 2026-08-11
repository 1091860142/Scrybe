"""按时长切 WAV，并计算精确累计偏移（纯 Python 实现，无需外部工具）。"""
from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    index: int
    path: Path
    start_ms: int  # 相对整段音频的精确起点（累计）
    end_ms: int


def split_wav(wav_path: Path, chunk_seconds: int, out_dir: Path) -> list[Chunk]:
    """把 16k 单声道 WAV 切成每块 <=chunk_seconds 秒，用帧数计算精确偏移。最后一块天然偏短。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        sw = wf.getsampwidth()
        ch = wf.getnchannels()
        bytes_per_sec = rate * sw * ch
        frames_per_chunk = rate * chunk_seconds

        chunks: list[Chunk] = []
        start = 0
        idx = 0
        while True:
            frames = wf.readframes(frames_per_chunk)
            if not frames:
                break
            p = out_dir / f"chunk_{idx:03d}.wav"
            with wave.open(str(p), "wb") as wf_out:
                wf_out.setnchannels(ch)
                wf_out.setsampwidth(sw)
                wf_out.setframerate(rate)
                wf_out.writeframes(frames)
            dur = len(frames) * 1000 // bytes_per_sec
            chunks.append(Chunk(index=idx, path=p, start_ms=start, end_ms=start + dur))
            start += dur
            idx += 1
    return chunks
