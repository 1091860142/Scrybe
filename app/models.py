"""核心数据模型，无任何依赖。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass
class Segment:
    """一条识别文本段。时间统一为整数毫秒（各 Provider 转换后进入此结构）。"""

    start_ms: int
    end_ms: int
    text: str


@dataclass
class ProviderResult:
    """一次识别调用的结果。"""

    segments: list[Segment] = field(default_factory=list)
    language: str = "zh"
    raw: dict = field(default_factory=dict)  # 原始响应，便于调试


class FileStatus(Enum):
    """单个文件的状态。"""

    PENDING = "等待中"
    PROCESSING = "处理中"
    SUCCESS = "成功"
    FAILED = "失败"
    CANCELED = "已取消"


@dataclass
class FileJob:
    """一个待转换的媒体文件。"""

    source: Path  # 输入媒体文件
    output_dir: Path  # 字幕输出目录
    status: FileStatus = FileStatus.PENDING
    size_bytes: int = 0
    error: str = ""
    progress: int = 0  # 0-100
