"""真实百炼 API 实测脚本。

用法：
  python tools/live_dashscope.py <媒体文件> [--api-key sk-xxx] [--language zh]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.audio_util import transcode_to_wav
from app.core.srt_builder import segments_to_srt
from app.providers.dashscope import DashScopeProvider


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("media", help="输入媒体文件")
    ap.add_argument("--api-key", default="", help="百炼 API Key（或用环境变量 DASHSCOPE_API_KEY）")
    ap.add_argument("--language", default="zh")
    args = ap.parse_args()

    api_key = args.api_key or os.environ.get("DASHSCOPE_API_KEY", "")

    if not api_key:
        print("请通过 --api-key 提供百炼 API Key")
        sys.exit(1)

    tmp = Path(tempfile.mkdtemp())
    try:
        wav = tmp / "audio.wav"
        print("正在转码…")
        transcode_to_wav(Path(args.media), wav)
        print(f"WAV: {wav.stat().st_size} 字节, 时长 {wav.stat().st_size * 1000 // 32000} ms")
        prov = DashScopeProvider(api_key=api_key)
        res = prov.transcribe_wav(wav, args.language, log=print)
        print("\n===== SRT =====")
        print(segments_to_srt(res.segments))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
