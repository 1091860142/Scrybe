"""真实 OpenAI 兼容接口实测脚本。

用法：
  python tools/live_openai.py <媒体文件> --base-url https://api.openai.com --api-key sk-xxx --model whisper-1
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.audio_util import transcode_to_wav
from app.core.srt_builder import segments_to_srt
from app.providers.openai_compat import OpenAICompatProvider


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("media", help="输入媒体文件")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--model", default="whisper-1")
    ap.add_argument("--language", default="zh")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp())
    try:
        wav = tmp / "audio.wav"
        print("正在转码…")
        transcode_to_wav(Path(args.media), wav)
        print(f"WAV: {wav.stat().st_size} 字节")
        prov = OpenAICompatProvider(base_url=args.base_url, api_key=args.api_key, model=args.model)
        res = prov.transcribe_wav(wav, args.language, log=print)
        print("\n===== SRT =====")
        print(segments_to_srt(res.segments))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
