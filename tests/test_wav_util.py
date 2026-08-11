"""WAV 时长读取单元测试。"""
import wave

from app.core.wav_util import read_wav_duration_ms


def test_duration(tmp_path):
    p = tmp_path / "t.wav"
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * (16000 * 3))  # 3 秒
    assert abs(read_wav_duration_ms(p) - 3000) < 20


def test_invalid_file(tmp_path):
    p = tmp_path / "not.wav"
    p.write_bytes(b"hello")
    try:
        read_wav_duration_ms(p)
    except ValueError:
        pass
    else:
        raise AssertionError("应抛出 ValueError")
