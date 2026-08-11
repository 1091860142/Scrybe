"""segments -> SRT 文本。"""
from __future__ import annotations

from app.models import Segment


def format_timestamp(ms: int) -> str:
    """毫秒 -> "HH:MM:SS,mmm"。"""
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, mmm = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{mmm:03d}"


def merge_segments(segments: list[Segment], merge_gap_ms: int = 400) -> list[Segment]:
    """排序、去空、相邻间隔小于阈值时合并为多行字幕。不修改入参对象。"""
    valid = [s for s in segments if s.text.strip() and s.end_ms - s.start_ms >= 50]
    valid.sort(key=lambda s: s.start_ms)
    merged: list[Segment] = []
    for s in valid:
        if merged and s.start_ms - merged[-1].end_ms < merge_gap_ms:
            prev = merged[-1]
            prev.end_ms = max(prev.end_ms, s.end_ms)
            prev.text = f"{prev.text}\n{s.text}"
        else:
            merged.append(Segment(s.start_ms, s.end_ms, s.text))
    return merged


def segments_to_srt(segments: list[Segment], merge_gap_ms: int = 400) -> str:
    """生成标准 SRT 文本（编号从 1 开始，字幕间空行）。"""
    cues = merge_segments(segments, merge_gap_ms)
    lines: list[str] = []
    for i, seg in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(seg.start_ms)} --> {format_timestamp(seg.end_ms)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)
