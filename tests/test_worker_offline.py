"""worker 两阶段编排（离线，FakeProvider + mock 转码）：并行提取 → 串行识别。"""
from __future__ import annotations

import threading
import wave
from pathlib import Path

import pytest

from PySide6.QtCore import QCoreApplication

from app.config import Config
from app.models import FileJob, ProviderResult, Segment
from app.providers.base import ASRProvider, ProviderCapability
from app.ui.worker import QueueWorker


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def _make_wav(path: Path, seconds: int = 2) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * (16000 * seconds))


class FakeProvider(ASRProvider):
    """记录识别调用顺序与最大并发。"""

    name = "fake"

    def __init__(self):
        self.calls: list[str] = []  # wav 缓存文件名（stem）
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def capability(self):
        return ProviderCapability(max_file_size_bytes=None)

    def transcribe_wav(self, wav_path, language, log=None, stop=None):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        threading.Event().wait(0.02)  # 制造重叠窗口
        self.calls.append(Path(wav_path).stem)
        with self.lock:
            self.active -= 1
        return ProviderResult(segments=[Segment(0, 1000, "句A")])


def test_parallel_extract_then_sequential_recognize(qt_app, monkeypatch, tmp_path):
    src_name: dict[str, str] = {}  # wav stem -> 源文件名
    state = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def fake_transcode(src, dst):
        src_name[Path(dst).stem] = src.name
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        threading.Event().wait(0.05)  # 制造重叠窗口
        _make_wav(dst)
        with lock:
            state["active"] -= 1

    monkeypatch.setattr("app.core.pipeline.transcode_to_wav", fake_transcode)

    provider = FakeProvider()
    monkeypatch.setattr("app.ui.worker.create_provider", lambda cfg: provider)

    jobs: list[FileJob] = []
    for i in range(4):
        src = tmp_path / f"f{i}.mp4"
        src.write_bytes(b"x")
        jobs.append(FileJob(source=src, output_dir=tmp_path / "out", size_bytes=10))

    worker = QueueWorker(jobs, Config(parallel_extractions=3))
    phases: list[str] = []
    done: list[str] = []
    worker.signals.queue_phase.connect(phases.append)
    worker.signals.file_done.connect(lambda i, r, d: done.append(r))
    worker.run()

    assert state["max_active"] >= 2, "音频提取应并行"
    assert provider.max_active == 1, "API 识别必须串行（一个返回后才识别下一个）"
    assert phases == ["extract", "recognize"]
    assert [src_name[s] for s in provider.calls] == [f"f{i}.mp4" for i in range(4)], "识别顺序应为队列顺序"
    assert done == ["success"] * 4
