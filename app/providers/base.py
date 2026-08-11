"""识别服务抽象层。"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models import ProviderResult


@dataclass
class ProviderCapability:
    """告诉管线是否需要切块。"""

    max_file_size_bytes: int | None = None  # None = 无大小限制（不切块）
    max_duration_sec: int | None = None


LogFn = Callable[[str], None]


class ASRProvider(ABC):
    name: str = "base"

    @abstractmethod
    def capability(self) -> ProviderCapability:
        ...

    @abstractmethod
    def transcribe_wav(
        self,
        wav_path: Path,
        language: str,
        log: LogFn | None = None,
        stop: threading.Event | None = None,
    ) -> ProviderResult:
        """返回相对给定 wav 起点(0-based)的 segments；块偏移由 pipeline 负责。"""
        ...


def create_provider(cfg) -> ASRProvider:
    """按配置创建 Provider。"""
    from app.providers.dashscope import DashScopeProvider
    from app.providers.openai_compat import OpenAICompatProvider

    if cfg.provider == "dashscope":
        return DashScopeProvider(api_key=cfg.dashscope_api_key)
    if cfg.provider == "openai_compat":
        return OpenAICompatProvider(
            base_url=cfg.openai_base_url,
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
        )
    raise ValueError(f"未知识别服务: {cfg.provider}")
