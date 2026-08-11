"""读 WAV 文件头算时长，无需 ffprobe。"""
from __future__ import annotations

import struct
from pathlib import Path


def read_wav_duration_ms(path: Path) -> int:
    """解析 RIFF 头：fmt 块取 byte_rate，data 块取数据长度。duration_ms = data_len*1000/byte_rate。"""
    with open(path, "rb") as f:
        head = f.read(12)
        if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError(f"不是有效的 WAV 文件: {path}")
        byte_rate: int | None = None
        data_len: int | None = None
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            chunk_id, chunk_size = struct.unpack("<4sI", hdr)
            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                # fmt 布局：audio_format(2) num_channels(2) sample_rate(4) byte_rate(4) block_align(2) bits(2)
                if len(fmt_data) >= 12:
                    byte_rate = struct.unpack("<I", fmt_data[8:12])[0]
                if chunk_size % 2:
                    f.read(1)
            elif chunk_id == b"data":
                data_len = chunk_size
                break
            else:
                f.seek(chunk_size + (chunk_size % 2), 1)
    if byte_rate is None or data_len is None:
        raise ValueError(f"WAV 缺少 fmt/data 块: {path}")
    if byte_rate <= 0:
        raise ValueError(f"WAV byte_rate 非法: {path}")
    return data_len * 1000 // byte_rate
