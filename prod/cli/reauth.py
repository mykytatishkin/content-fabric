"""CLI entry point for YouTube OAuth re-authorization.

Uses Selenium + undetected-chromedriver for automated login when credentials
are available, otherwise opens a browser for manual authorization.

Usage:
    python -m cli.reauth --channel-id 9
    python -m cli.reauth --channel-id 9 46 49
    python -m cli.reauth --all-failed
    python -m cli.reauth --all
    python -m cli.reauth --channel-id 9 --no-browser   # remote server (print URL only)
    python -m cli.reauth --channel-id 9 --port 9090     # custom callback port
"""

from __future__ import annotations

import argparse
import sys

import shared.env  # noqa: F401 — load .env files

from shared.logging_config import setup_logging
from shared.youtube.reauth.service import YouTubeReauthService, ServiceConfig, OAuthSettings
from shared.youtube.reauth.models import ReauthStatus
from shared.db.repositories import channel_repo, audit_repo

import logging

logger = logging.getLogger(__name__)


def get_failed_channel_ids() -> list[int]:
    """Get channel IDs that have recent failed reauth or token errors."""
    channels = channel_repo.get_all_channels(enabled_only=True)
    failed_ids = []
    for ch in channels:
        if not ch.get("access_token") or not ch.get("refresh_token"):
            failed_ids.append(ch["id"])
            continue
        audits = audit_repo.get_recent_reauth_audits(ch["id"], limit=1)
        if audits and audits[0].get("status") in ("failed", "skipped"):
            failed_ids.append(ch["id"])
    return failed_ids


def main() -> None:
    setup_logging(service_name="cff-reauth")

    parser = argparse.ArgumentParser(
        description="YouTube OAuth re-authorization (opens browser for manual auth)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--channel-id", type=int, nargs="+", help="Channel ID(s) to re-authorize")
    group.add_argument("--all-failed", action="store_true", help="Re-authorize all channels with failed tokens")
    group.add_argument("--all", action="store_true", help="Re-authorize all enabled channels")
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't open browser automatically (print URL for remote server usage)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run Selenium in headless mode (no visible browser window)",
    )
    parser.add_argument("--port", type=int, default=8080, help="OAuth callback port (default: 8080)")
    parser.add_argument("--timeout", type=int, default=300, help="OAuth timeout in seconds (default: 300)")
    args = parser.parse_args()

    if args.channel_id:
        channel_ids = args.channel_id
    elif args.all_failed:
        channel_ids = get_failed_channel_ids()
        if not channel_ids:
            logger.info("No channels with failed tokens found")
            print("No channels with failed tokens found.")
            return
        logger.info("Found %d channels with failed tokens: %s", len(channel_ids), channel_ids)
    elif args.all:
        channels = channel_repo.get_all_channels(enabled_only=True)
        channel_ids = [ch["id"] for ch in channels]
        if not channel_ids:
            logger.info("No enabled channels found")
            print("No enabled channels found.")
            return
        logger.info("Re-authorizing all %d enabled channels", len(channel_ids))
    else:
        parser.print_help()
        sys.exit(1)

    config = ServiceConfig(
        oauth_settings=OAuthSettings(
            redirect_port=args.port,
            timeout_seconds=args.timeout,
        ),
        open_browser=not args.no_browser,
        headless=args.headless,
    )

    if args.no_browser:
        print("\nРежим без браузера: відкрийте посилання вручну.")
        print("Для віддаленого сервера використовуйте SSH тунель:")
        print(f"  ssh -L {args.port}:localhost:{args.port} user@server\n")

    service = YouTubeReauthService(service_config=config)
    results = service.run_sync(channel_ids)

    success = sum(1 for r in results if r.status == ReauthStatus.SUCCESS)
    failed = sum(1 for r in results if r.status == ReauthStatus.FAILED)
    skipped = sum(1 for r in results if r.status == ReauthStatus.SKIPPED)

    print(f"\nReauth complete: {success} success, {failed} failed, {skipped} skipped")
    for r in results:
        status_icon = {"success": "+", "failed": "X", "skipped": "~"}[r.status.value]
        print(f"  [{status_icon}] {r.channel_name}: {r.status.value}")
        if r.error:
            print(f"      Error: {r.error}")


if __name__ == "__main__":
    main()
