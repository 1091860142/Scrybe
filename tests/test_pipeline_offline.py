"""管线端到端（离线，FakeProvider + mock ffmpeg）。"""
import shutil
import threading
import wave

from app.config import Config
from app.core.audio_chunker import Chunk
from app.core.pipeline import Pipeline
from app.models import FileJob, ProviderResult, Segment
from app.providers.base import ASRProvider, ProviderCapability


def _make_wav(path, seconds=2):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * (16000 * seconds))


class FakeProvider(ASRProvider):
    name = "fake"

    def capability(self):
        return ProviderCapability(max_file_size_bytes=None)

    def transcribe_wav(self, wav_path, language, log=None, stop=None):
        return ProviderResult(
            segments=[
                Segment(0, 1500, "第一句"),
                Segment(2500, 4000, "第二句"),
            ]
        )


def test_single_chunk(monkeypatch, tmp_path):
    src = tmp_path / "测试 视频.mp4"
    src.write_bytes(b"dummy")
    wav = tmp_path / "pre.wav"
    _make_wav(wav)
    monkeypatch.setattr("app.core.pipeline.transcode_to_wav", lambda s, d: shutil.copyfile(wav, d))

    out_dir = tmp_path / "out"
    job = FileJob(source=src, output_dir=out_dir, size_bytes=10)
    pipe = Pipeline(Config(), FakeProvider())
    out = pipe.process_file(job, progress=lambda p: None, log=lambda l, m: None, stop=threading.Event())

    assert out == out_dir / "测试 视频.srt"
    text = out.read_text(encoding="utf-8-sig")
    assert "00:00:00,000 --> 00:00:01,500" in text
    assert "00:00:02,500 --> 00:00:04,000" in text
    assert "第一句" in text and "第二句" in text


class LimProvider(ASRProvider):
    name = "lim"

    def capability(self):
        return ProviderCapability(max_file_size_bytes=10)  # 强制切块

    def transcribe_wav(self, wav_path, language, log=None, stop=None):
        return ProviderResult(segments=[Segment(0, 1000, "句A")])


def test_two_chunks_offset_merge(monkeypatch, tmp_path):
    src = tmp_path / "long.mp4"
    src.write_bytes(b"dummy")
    wav = tmp_path / "pre.wav"
    _make_wav(wav)
    monkeypatch.setattr("app.core.pipeline.transcode_to_wav", lambda s, d: shutil.copyfile(wav, d))
    chunks = [Chunk(0, wav, 0, 8000), Chunk(1, wav, 8000, 16000)]
    monkeypatch.setattr("app.core.pipeline.split_wav", lambda w, s, o: chunks)

    out_dir = tmp_path / "out"
    job = FileJob(source=src, output_dir=out_dir, size_bytes=10)
    pipe = Pipeline(Config(chunk_seconds=8), LimProvider())
    out = pipe.process_file(job, progress=lambda p: None, log=lambda l, m: None, stop=threading.Event())

    text = out.read_text(encoding="utf-8-sig")
    assert "00:00:00,000 --> 00:00:01,000" in text  # 第一块
    assert "00:00:08,000 --> 00:00:09,000" in text  # 第二块偏移 +8000
