"""配置读写：%APPDATA%\\Scrybe\\config.json。"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Config:
    provider: str = "dashscope"  # "dashscope" | "openai_compat"
    language: str = "zh"  # "zh" | "en" | "auto"
    output_dir: str = ""  # 空 -> 使用默认输出目录
    dashscope_api_key: str = ""
    openai_base_url: str = "https://api.openai.com"
    openai_api_key: str = ""
    openai_model: str = "whisper-1"
    chunk_seconds: int = 600  # OpenAI 兼容切块时长
    merge_gap_ms: int = 400  # SRT 合并阈值
    parallel_extractions: int = 2  # 并行提取音频的文件数


def config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Scrybe" / "config.json"


def default_output_dir() -> Path:
    return Path.home() / "Documents" / "字幕"


def load_config() -> Config:
    """读取配置；缺失或损坏时返回默认值。"""
    p = config_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            valid = {k: v for k, v in data.items() if k in Config.__dataclass_fields__}
            return Config(**valid)
        except Exception:
            pass  # 损坏则回退默认
    return Config()


def save_config(cfg: Config) -> None:
    """原子写入配置（先写临时文件再替换）。"""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
