"""音频提取与转码（基于 PyAV，内置 FFmpeg 解码库，无需外部二进制）。"""
from __future__ import annotations

import ctypes
import wave
from pathlib import Path

import av


class AudioError(Exception):
    """音频处理失败。"""


def _frame_to_bytes(frame) -> bytes:
    """从 AudioFrame 取 PCM 原始字节（不依赖 numpy）。av>=15 的 Plane 通过 buffer_ptr 暴露内存。"""
    return b"".join(ctypes.string_at(p.buffer_ptr, p.buffer_size) for p in frame.planes)


def transcode_to_wav(src: Path, dst: Path) -> None:
    """统一转码为 16kHz 单声道 PCM WAV（约 1.875MB/分钟），支持绝大多数音视频格式。"""
    try:
        container = av.open(str(src))
    except Exception as e:
        raise AudioError(f"无法打开文件 {src.name}: {e}") from e
    try:
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if audio_stream is None:
            raise AudioError(f"文件中没有音频流: {src.name}")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        with wave.open(str(dst), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            try:
                for frame in container.decode(audio_stream):
                    for out in resampler.resample(frame):
                        wf.writeframes(_frame_to_bytes(out))
            except av.FFmpegError as e:
                raise AudioError(f"解码音频失败: {e}") from e
            # 冲刷重采样残留
            for out in resampler.resample(None) or []:
                wf.writeframes(_frame_to_bytes(out))
    finally:
        container.close()
