"""CLI entry point for OpenAI TTS synthesis.

Usage:
    python -m cli.tts --text "Привет, мир" --out /tmp/hello.mp3
    python -m cli.tts --input story.txt --out /tmp/story.mp3 --voice nova --language ru
    python -m cli.tts --text "..." --out /tmp/x.mp3 --instructions "Speak slowly"

On success: print absolute output path and exit 0.
On failure: print error to stderr and exit nonzero.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cli.tts",
        description="Synthesize text via OpenAI TTS and write to MP3 (or other format).",
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--text", help="Inline text to synthesize")
    grp.add_argument("--input", help="Path to a UTF-8 text file to synthesize")

    p.add_argument("--out", required=True, help="Output audio path")
    p.add_argument("--voice", default="nova",
                   help="OpenAI voice name (default: nova)")
    p.add_argument("--language", default=None,
                   help="Language hint (ru/uk/en/...) — used in instructions if --instructions is unset")
    p.add_argument("--instructions", default=None,
                   help="Free-form style instructions (overrides --language hint)")
    p.add_argument("--model", default="gpt-4o-mini-tts",
                   help="OpenAI model id (default: gpt-4o-mini-tts)")
    p.add_argument("--format", default="mp3", dest="response_format",
                   choices=["mp3", "wav", "opus", "aac", "flac", "pcm"],
                   help="Response format (default: mp3)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Playback speed 0.25..4.0 (default: 1.0)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Resolve text source
    if args.text is not None:
        text = args.text
    else:
        try:
            text = Path(args.input).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read --input: {exc}", file=sys.stderr)
            return 2

    if not text.strip():
        print("error: text is empty", file=sys.stderr)
        return 2

    # Late import so --help works without env / openai installed
    try:
        import shared.env  # noqa: F401  (loads .env)
    except Exception:
        pass

    try:
        from shared.tts.openai_tts import synthesize
    except ImportError as exc:
        print(f"error: cannot import shared.tts.openai_tts: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out).expanduser().resolve()

    try:
        result = synthesize(
            text,
            out_path,
            voice=args.voice,
            model=args.model,
            language=args.language,
            instructions=args.instructions,
            response_format=args.response_format,
            speed=args.speed,
        )
    except Exception as exc:
        print(f"error: synthesis failed: {exc}", file=sys.stderr)
        return 1

    print(str(Path(result).resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
