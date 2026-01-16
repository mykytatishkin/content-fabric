#!/usr/bin/env python3
"""
Run automated YouTube OAuth re-authentication flow.

Usage examples:
    python run_youtube_reauth.py "Ютуб5.0"
    python run_youtube_reauth.py --all-expiring
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (Telegram credentials, DB overrides, etc.)
load_dotenv()

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.youtube_reauth_service import main as run_service  # noqa: E402
from core.utils.logger import get_logger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Delegate to the CLI runner and provide user-friendly error handling."""
    logger = get_logger("run_youtube_reauth")

    print("=" * 72)
    print("YouTube OAuth Re-authentication Service")
    print("=" * 72)
    print()

    try:
        exit_code = run_service(argv)
        if exit_code == 0:
            print("\n✅ Re-auth service completed.")
            logger.info("Re-auth service completed successfully")
        else:
            print("\n❌ Re-auth service reported failures. See logs for details.")
            logger.error("Re-auth service completed with failures")
        return exit_code
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user.")
        logger.warning("Re-auth service interrupted by user")
        return 1
    except Exception as exc:  # pragma: no cover - defensive output
        print(f"\n❌ Unexpected error: {exc}")
        logger.exception("Unexpected error during re-auth service")
        return 1


if __name__ == "__main__":
    sys.exit(main())


