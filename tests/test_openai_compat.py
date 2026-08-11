"""OpenAI 兼容 Provider 单元测试（离线 mock）。"""
from app.providers.openai_compat import OpenAICompatProvider


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _make_wav(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"fake")
    return wav


def test_parse_verbose_json(monkeypatch, tmp_path):
    wav = _make_wav(tmp_path)

    def fake_request(method, url, **kw):
        assert url.endswith("/v1/audio/transcriptions")
        return FakeResp(
            {
                "segments": [
                    {"start": 0.0, "end": 1.2, "text": "你好"},
                    {"start": 2.0, "end": 3.5, "text": " 世界 "},
                ]
            }
        )

    monkeypatch.setattr("app.providers.openai_compat.requests.request", fake_request)
    prov = OpenAICompatProvider("https://example.com", "sk-test", "whisper-1")
    res = prov.transcribe_wav(wav, "zh")
    assert len(res.segments) == 2
    assert res.segments[0].start_ms == 0
    assert res.segments[0].end_ms == 1200
    assert res.segments[0].text == "你好"
    assert res.segments[1].start_ms == 2000
    assert res.segments[1].end_ms == 3500
    assert res.segments[1].text == "世界"


def test_empty_segments(monkeypatch, tmp_path):
    wav = _make_wav(tmp_path)
    monkeypatch.setattr(
        "app.providers.openai_compat.requests.request",
        lambda *a, **k: FakeResp({"segments": []}),
    )
    prov = OpenAICompatProvider("https://example.com", "sk", "whisper-1")
    assert prov.transcribe_wav(wav, "zh").segments == []
