"""SRT 生成器单元测试。"""
from app.core.srt_builder import format_timestamp, merge_segments, segments_to_srt
from app.models import Segment


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(1200) == "00:00:01,200"
    assert format_timestamp(61000) == "00:01:01,000"
    assert format_timestamp(3599999) == "00:59:59,999"
    assert format_timestamp(-5) == "00:00:00,000"


def test_segments_to_srt_exact():
    srt = segments_to_srt([Segment(1000, 4200, "你好，世界")], merge_gap_ms=400)
    assert srt == "1\n00:00:01,000 --> 00:00:04,200\n你好，世界\n"


def test_two_cues():
    srt = segments_to_srt(
        [Segment(0, 1500, "第一句"), Segment(2500, 4000, "第二句")], merge_gap_ms=400
    )
    assert srt == (
        "1\n00:00:00,000 --> 00:00:01,500\n第一句\n\n"
        "2\n00:00:02,500 --> 00:00:04,000\n第二句\n"
    )


def test_merge_close_gap():
    merged = merge_segments([Segment(0, 1000, "A"), Segment(1200, 2000, "B")], 400)
    assert len(merged) == 1
    assert merged[0].text == "A\nB"
    assert merged[0].end_ms == 2000


def test_no_merge_far_gap():
    merged = merge_segments([Segment(0, 1000, "A"), Segment(2000, 3000, "B")], 400)
    assert len(merged) == 2


def test_drops_empty_and_tiny():
    segs = [
        Segment(0, 10, "x"),  # 过短
        Segment(100, 200, "   "),  # 空白
        Segment(1000, 2000, "ok"),
    ]
    merged = merge_segments(segs)
    assert len(merged) == 1
    assert merged[0].text == "ok"


def test_input_not_mutated():
    segs = [Segment(0, 1000, "A"), Segment(1200, 2000, "B")]
    segments_to_srt(segs)
    assert segs[0].end_ms == 1000
    assert len(segs) == 2
