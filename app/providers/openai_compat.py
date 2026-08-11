"""OpenAI 兼容接口：POST {base}/v1/audio/transcriptions。"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import requests

from app.models import ProviderResult, Segment
from app.providers.base import ASRProvider, LogFn, ProviderCapability

# OpenAI 官方单次上传约 25MB，留 1MB 余量
MAX_FILE_SIZE = 24 * 1024 * 1024


class OpenAICompatProvider(ASRProvider):
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def capability(self) -> ProviderCapability:
        return ProviderCapability(max_file_size_bytes=MAX_FILE_SIZE)

    def transcribe_wav(
        self,
        wav_path: Path,
        language: str,
        log: LogFn | None = None,
        stop: threading.Event | None = None,
    ) -> ProviderResult:
        url = f"{self.base_url}/v1/audio/transcriptions"
        data: dict = {"model": self.model, "response_format": "verbose_json"}
        if language and language != "auto":
            data["language"] = language
        with open(wav_path, "rb") as fh:
            files = {"file": (wav_path.name, fh, "audio/wav")}
            resp = _request_with_retry(
                "POST",
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=data,
                log=log,
                stop=stop,
            )
        payload = resp.json()
        segments = []
        for seg in payload.get("segments") or []:
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                Segment(
                    start_ms=round(float(seg["start"]) * 1000),
                    end_ms=round(float(seg["end"]) * 1000),
                    text=text,
                )
            )
        return ProviderResult(segments=segments, language=language or "zh", raw=payload)


def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict,
    log: LogFn | None,
    stop: threading.Event | None,
    files: dict | None = None,
    data: dict | None = None,
    retries: int = 3,
    base_delay: float = 2.0,
) -> requests.Response:
    """429/5xx 重试（2s/4s/8s 退避），重试间检查停止标志。"""
    last_err: Exception | None = None
    for attempt in range(retries):
        if stop is not None and stop.is_set():
            raise RuntimeError("用户已停止")
        try:
            resp = requests.request(
                method, url, headers=headers, files=files, data=data, timeout=(10, 600)
            )
        except requests.RequestException as e:
            last_err = e
            if attempt == retries - 1:
                break
            delay = base_delay * 2**attempt
            if log:
                log(f"网络错误，{delay:.0f}s 后重试: {e}")
            _sleep_interruptible(delay, stop)
            continue
        if resp.status_code in (429,) or resp.status_code >= 500:
            if attempt == retries - 1:
                last_err = _HttpStatusError(resp)
                break
            delay = base_delay * 2**attempt
            if log:
                log(f"服务端 {resp.status_code}，{delay:.0f}s 后重试")
            _sleep_interruptible(delay, stop)
            continue
        resp.raise_for_status()
        return resp
    if isinstance(last_err, _HttpStatusError):
        raise RuntimeError(f"请求失败(HTTP {last_err.resp.status_code}): {last_err.resp.text[:300]}")
    raise RuntimeError(f"网络请求失败: {last_err}") from last_err


class _HttpStatusError(Exception):
    def __init__(self, resp: requests.Response):
        super().__init__(f"HTTP {resp.status_code}")
        self.resp = resp


def _sleep_interruptible(sec: float, stop: threading.Event | None) -> None:
    end = time.monotonic() + sec
    while time.monotonic() < end:
        if stop is not None and stop.is_set():
            return
        time.sleep(0.1)
