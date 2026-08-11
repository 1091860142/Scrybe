"""阿里云百炼 Paraformer 语音识别。

采用官方 dashscope SDK 的 Recognition（WebSocket 实时流式），支持直接传本地音频文件，
无需 OSS/公网 URL。返回句子级 begin_time/end_time（毫秒）。
实测确认：模型 paraformer-realtime-v2，format=wav，sample_rate=16000。
"""
from __future__ import annotations

import threading
from pathlib import Path

from app.models import ProviderResult, Segment
from app.providers.base import ASRProvider, LogFn, ProviderCapability


class DashScopeProvider(ASRProvider):
    name = "dashscope"

    def __init__(self, api_key: str, model: str = "paraformer-realtime-v2"):
        self.api_key = api_key
        self.model = model

    def capability(self) -> ProviderCapability:
        # WebSocket 流式无上传大小限制；单个 30 分钟内文件直接整体识别
        return ProviderCapability(max_file_size_bytes=None)

    def transcribe_wav(
        self,
        wav_path: Path,
        language: str,
        log: LogFn | None = None,
        stop: threading.Event | None = None,
    ) -> ProviderResult:
        import dashscope
        from dashscope.audio.asr import Recognition, RecognitionCallback

        if not self.api_key:
            raise RuntimeError("未配置阿里云百炼 API Key")
        dashscope.api_key = self.api_key

        kwargs: dict = {}
        if language and language != "auto":
            kwargs["language_hints"] = [language]

        rec = Recognition(
            model=self.model,
            callback=RecognitionCallback(),  # call() 同步模式下不使用回调
            format="wav",
            sample_rate=16000,
            **kwargs,
        )
        result = rec.call(file=str(wav_path))
        if result.status_code != 200:
            msg = (result.message or result.code or "未知错误").strip()
            raise RuntimeError(f"百炼识别失败: {msg}")

        segments: list[Segment] = []
        for s in result.get_sentence() or []:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                Segment(
                    start_ms=int(s.get("begin_time") or 0),
                    end_ms=int(s.get("end_time") or 0),
                    text=text,
                )
            )
        return ProviderResult(segments=segments, language=language or "zh")
