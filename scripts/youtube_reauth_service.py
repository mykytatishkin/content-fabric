#!/usr/bin/env python3
"""Command-line runner for the automated YouTube OAuth re-authentication service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta

from core.auth.reauth.service import ServiceConfig, YouTubeReauthService  # noqa: E402
from core.database.mysql_db import get_mysql_database  # noqa: E402
from core.utils.logger import get_logger  # noqa: E402

LOGGER = get_logger("youtube_reauth_runner")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run automated YouTube OAuth re-authentication for one or more channels.",
    )
    parser.add_argument(
        "channels",
        metavar="CHANNEL",
        nargs="*",
        help="Channel name(s) as stored in MySQL youtube_channels.name",
    )
    parser.add_argument(
        "--all-expiring",
        action="store_true",
        help="Automatically select enabled channels whose tokens are expired or missing.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chromium in headless mode (default is headful for easier debugging).",
    )
    parser.add_argument(
        "--redirect-port",
        type=int,
        default=8080,
        help="Local port for OAuth callback (default: 8080).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max seconds to wait for OAuth consent before timing out (default: 300).",
    )
    return parser.parse_args(argv)


def resolve_channels(args: argparse.Namespace, db) -> list[str]:
    if args.channels:
        return args.channels

    if args.all_expiring:
        expiring = db.get_expired_tokens()
        if expiring:
            LOGGER.info("Automatically selected %d expiring channels.", len(expiring))
            return expiring
        LOGGER.info("No channels with expired tokens found.")
        return []

    raise SystemExit("No channels provided. Pass channel names or use --all-expiring.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    db = get_mysql_database()

    channels = resolve_channels(args, db)
    if not channels:
        LOGGER.info("Nothing to do.")
        return 0

    service_config = ServiceConfig()
    service_config.browser.headless = args.headless
    service_config.oauth_settings.redirect_port = args.redirect_port
    service_config.oauth_settings.timeout_seconds = args.timeout

    service = YouTubeReauthService(db=db, service_config=service_config)

    results = service.run_sync(channels)

    success = [r for r in results if r.status == r.status.SUCCESS]
    failures = [r for r in results if r.status != r.status.SUCCESS]

    # Save tokens to database for successful reauths
    for result in success:
        if result.access_token and result.refresh_token:
            expires_at = None
            if result.expires_in:
                expires_at = datetime.now() + timedelta(seconds=result.expires_in)
            
            saved = db.update_channel_tokens(
                name=result.channel_name,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                expires_at=expires_at
            )
            if saved:
                LOGGER.info("Tokens saved to database for channel %s", result.channel_name)
            else:
                LOGGER.warning("Failed to save tokens to database for channel %s", result.channel_name)

    LOGGER.info("Reauth finished: %d success, %d failed", len(success), len(failures))
    for result in failures:
        LOGGER.error(
            "Channel %s failed: %s",
            result.channel_name,
            result.error,
        )

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())


