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
        # Get channels with tokens expiring within 3 days or already expired
        expiring = db.get_expiring_tokens(days_ahead=3)
        if expiring:
            LOGGER.info("Automatically selected %d expiring channels.", len(expiring))
            return expiring
        LOGGER.info("No channels with expiring tokens found.")
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
            
            # Save profile_path if it was used during reauth
            # Get credential to check if profile_path was set
            credential = db.get_account_credentials(result.channel_name, include_disabled=True)
            if credential:
                from pathlib import Path
                project_root = Path(__file__).parent.parent
                
                # Determine the actual profile directory path
                if credential.profile_path:
                    # If profile_path is set, use it but ensure it's a directory path
                    profile_path_obj = Path(credential.profile_path)
                    # Check if it's a file path (has extension like .json) or is actually a file
                    if profile_path_obj.suffix and profile_path_obj.suffix.lower() in ['.json', '.txt', '.log']:
                        # If it's a file path, use parent directory
                        actual_profile_path = str(profile_path_obj.parent)
                    elif profile_path_obj.is_file():
                        # If it exists and is a file, use parent directory
                        actual_profile_path = str(profile_path_obj.parent)
                    else:
                        # It's already a directory path
                        actual_profile_path = credential.profile_path
                else:
                    # If profile_path is not set, create default path
                    actual_profile_path = str(project_root / "data" / "profiles" / result.channel_name)
                
                # Ensure the directory exists
                Path(actual_profile_path).mkdir(parents=True, exist_ok=True)
                
                # Update profile_path in database if it changed or was empty
                if not credential.profile_path or credential.profile_path != actual_profile_path:
                    profile_saved = db.update_profile_path(result.channel_name, actual_profile_path)
                    if profile_saved:
                        LOGGER.info("Profile path saved to database for channel %s: %s", 
                                  result.channel_name, actual_profile_path)
                    else:
                        LOGGER.warning("Failed to save profile path for channel %s", result.channel_name)
                else:
                    # Profile path already set correctly
                    LOGGER.debug("Profile path already set for channel %s: %s", 
                               result.channel_name, actual_profile_path)

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


