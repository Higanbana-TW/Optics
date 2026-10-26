from __future__ import annotations

import argparse
import sys

from live_captions import __version__
from live_captions.config import (
    configure_logging,
    env_file,
    load_config,
    load_dotenv,
    load_settings,
    public_summary,
    resolve_audio,
    windows_banner,
)
from live_captions.errors import CaptionsError
from live_captions.paths import data_dir
from live_captions.runtime import DEMO_LINES, list_audio, run_app, run_headless_lines, run_setup
from live_captions.translate.traditional import TraditionalConverter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="live_captions",
        description="Windows 浮動雙語字幕：聽取系統播放的英文，同時顯示繁體中文。",
    )
    parser.add_argument("--audio", choices=["loopback", "mic"], default=None)
    parser.add_argument("--demo", action="store_true", help="不聽音訊，改以幾句範例英文翻譯")
    parser.add_argument("--headless", action="store_true", help="不要開啟字幕視窗，只把結果印出來")
    parser.add_argument("--convert", metavar="TEXT", help="把中文轉成台灣繁體後印出")
    parser.add_argument("--translate", metavar="TEXT", help="翻譯這句英文並印出繁體中文")
    parser.add_argument("--setup", action="store_true", help="下載語音與翻譯模型後結束")
    parser.add_argument("--list-audio", action="store_true", help="列出系統迴路與麥克風")
    parser.add_argument("--verbose", action="store_true", help="記錄辨識出的句子；預設不寫入字幕內容")
    parser.add_argument("--version", action="version", version=f"Optic 即時字幕 {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        configure_logging(args.verbose)
        load_dotenv(env_file())
        if args.convert is not None:
            print(TraditionalConverter().to_taiwan(args.convert))
            return 0
        if args.list_audio:
            return list_audio()
        config = load_config()
        if args.verbose:
            print(public_summary(config), file=sys.stderr)
        if args.setup:
            return run_setup(config)
        if args.translate is not None:
            return run_headless_lines(config, [args.translate])
        if args.demo and args.headless:
            return run_headless_lines(config, DEMO_LINES)
        if args.headless:
            print("請加上 --demo、--translate 或 --convert。", file=sys.stderr)
            return 2
        settings_path = data_dir() / "settings.json"
        existed = settings_path.is_file()
        settings = load_settings(settings_path)
        settings.audio = resolve_audio(
            cli=args.audio,
            settings=settings,
            settings_existed=existed,
            env_audio=config.audio,
        )
        print(f"Optic 即時字幕 {__version__}")
        print(public_summary(config))
        print(windows_banner())
        return run_app(config, settings, settings_path, demo=args.demo)
    except CaptionsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
