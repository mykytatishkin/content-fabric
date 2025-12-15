#!/usr/bin/env python3
"""Command-line runner for the automated YouTube OAuth re-authentication service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
from typing import Optional, Dict  # noqa: E402

from core.auth.reauth.service import ServiceConfig, YouTubeReauthService  # noqa: E402
from core.auth.reauth.models import ReauthResult  # noqa: E402
from core.database.mysql_db import get_mysql_database  # noqa: E402
from core.utils.logger import get_logger  # noqa: E402
import requests  # noqa: E402

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


def verify_channel_from_token(access_token: str) -> Optional[Dict[str, str]]:
    """
    Verify which YouTube channel an access token belongs to.
    
    Args:
        access_token: OAuth access token
        
    Returns:
        Dict with 'channel_id' (UC...) and 'custom_url' (if available), or None if failed
    """
    try:
        # Call YouTube API to get channel information
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "id,snippet",
            "mine": "true",
            "access_token": access_token
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            if items and len(items) > 0:
                channel_info = items[0]
                channel_id = channel_info.get("id")
                
                # Get custom URL if available
                snippet = channel_info.get("snippet", {})
                custom_url = snippet.get("customUrl")
                
                result = {"channel_id": channel_id}
                if custom_url:
                    result["custom_url"] = custom_url
                    LOGGER.info(f"Token belongs to channel ID: {channel_id}, custom URL: {custom_url}")
                else:
                    LOGGER.info(f"Token belongs to channel ID: {channel_id} (no custom URL)")
                
                return result
            else:
                LOGGER.warning("YouTube API returned no channels for token")
                return None
        else:
            LOGGER.error(f"Failed to verify channel from token: HTTP {response.status_code} - {response.text}")
            return None
    except Exception as e:
        LOGGER.error(f"Error verifying channel from token: {e}")
        return None


def save_reauth_tokens_to_db(db, result: ReauthResult) -> bool:
    """
    Save re-authentication tokens to database.
    This is the same logic used in main() function.
    
    IMPORTANT: Verifies that tokens belong to the expected channel.
    If multiple channels share the same Google account, ensures tokens
    are saved to the correct channel record.
    
    Args:
        db: YouTubeMySQLDatabase instance
        result: ReauthResult from re-authentication
        
    Returns:
        True if tokens were saved successfully, False otherwise
    """
    if not result.access_token:
        LOGGER.warning("No access_token in result for channel %s, skipping token save", result.channel_name)
        return False
    
    # Get expected channel from database
    expected_channel = db.get_channel(result.channel_name)
    if not expected_channel:
        LOGGER.error("Channel '%s' not found in database", result.channel_name)
        return False
    
    # Verify which channel the token actually belongs to
    actual_channel_info = verify_channel_from_token(result.access_token)
    if not actual_channel_info:
        LOGGER.error(
            "Failed to verify channel from token for %s. "
            "Tokens will NOT be saved to prevent saving to wrong channel.",
            result.channel_name
        )
        return False
    
    actual_channel_id = actual_channel_info.get("channel_id")
    actual_custom_url = actual_channel_info.get("custom_url")
    
    # Check if the token belongs to the expected channel
    expected_channel_id = expected_channel.channel_id
    
    # Normalize channel IDs for comparison (remove @ prefix if present)
    def normalize_channel_identifier(identifier: str) -> str:
        """Normalize channel ID or custom URL for comparison."""
        if not identifier:
            return ""
        return identifier.lstrip('@').lower()
    
    expected_normalized = normalize_channel_identifier(expected_channel_id)
    actual_id_normalized = normalize_channel_identifier(actual_channel_id)
    actual_url_normalized = normalize_channel_identifier(actual_custom_url) if actual_custom_url else None
    
    # Check if token belongs to expected channel by ID or custom URL
    matches_by_id = expected_normalized == actual_id_normalized
    matches_by_url = actual_url_normalized and expected_normalized == actual_url_normalized
    
    if not (matches_by_id or matches_by_url):
        # Token doesn't match expected channel - find the correct channel
        correct_channel = None
        
        # First try by channel_id
        if actual_channel_id:
            correct_channel = db.get_channel_by_channel_id(actual_channel_id)
        
        # If not found by ID and we have custom URL, try to find by custom URL
        if not correct_channel and actual_custom_url:
            # Search all channels for matching custom URL
            all_channels = db.get_all_channels()
            for channel in all_channels:
                channel_normalized = normalize_channel_identifier(channel.channel_id)
                if channel_normalized == actual_url_normalized:
                    correct_channel = channel
                    break
        
        if correct_channel:
            LOGGER.error(
                "⚠️  CRITICAL: Token belongs to channel '%s' (ID: %s%s), but reauth was requested for '%s' (ID: %s). "
                "This happens when multiple channels share the same Google account and wrong channel was selected during OAuth. "
                "Tokens will be saved to the CORRECT channel '%s' instead.",
                correct_channel.name,
                actual_channel_id,
                f", custom URL: {actual_custom_url}" if actual_custom_url else "",
                result.channel_name,
                expected_channel_id,
                correct_channel.name
            )
            
            # Save to the correct channel instead
            result.channel_name = correct_channel.name
        else:
            LOGGER.error(
                "⚠️  CRITICAL: Token belongs to channel ID '%s'%s, but no channel with this identifier found in database. "
                "Expected channel '%s' has ID '%s'. "
                "Tokens will NOT be saved to prevent data corruption.",
                actual_channel_id,
                f" (custom URL: {actual_custom_url})" if actual_custom_url else "",
                result.channel_name,
                expected_channel_id
            )
            return False
    else:
        match_type = "ID" if matches_by_id else "custom URL"
        LOGGER.info(
            "✅ Verified: Token belongs to expected channel '%s' (%s: %s)",
            result.channel_name,
            match_type,
            actual_channel_id if matches_by_id else actual_custom_url
        )
    
    # Check if refresh_token is present
    if not result.refresh_token:
        LOGGER.warning(
            "No refresh_token returned for channel %s. "
            "This may happen if user is already authorized. "
            "Access token will be saved but may expire without refresh capability.",
            result.channel_name
        )
        # Still save access_token even without refresh_token
        # Use existing refresh_token from database if available
        existing_channel = db.get_channel(result.channel_name)
        refresh_token_to_save = existing_channel.refresh_token if existing_channel else None
        
        if not refresh_token_to_save:
            LOGGER.error(
                "No refresh_token available for channel %s. "
                "Token will expire and cannot be refreshed automatically.",
                result.channel_name
            )
    else:
        refresh_token_to_save = result.refresh_token
        LOGGER.info("New refresh_token received for channel %s", result.channel_name)
    
    expires_at = None
    if result.expires_in:
        expires_at = datetime.now() + timedelta(seconds=result.expires_in)
    
    saved = db.update_channel_tokens(
        name=result.channel_name,
        access_token=result.access_token,
        refresh_token=refresh_token_to_save,  # May be None if not provided
        expires_at=expires_at
    )
    if saved:
        if refresh_token_to_save:
            LOGGER.info("Tokens (access_token + refresh_token) saved to database for channel %s", result.channel_name)
        else:
            LOGGER.warning("Access token saved for channel %s, but NO refresh_token available", result.channel_name)
    else:
        LOGGER.warning("Failed to save tokens to database for channel %s", result.channel_name)
        return False
    
    # Save profile_path if it was used during reauth
    credential = db.get_account_credentials(result.channel_name, include_disabled=True)
    if credential:
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        
        # Determine the actual profile directory path
        if credential.profile_path:
            profile_path_obj = Path(credential.profile_path)
            if profile_path_obj.suffix and profile_path_obj.suffix.lower() in ['.json', '.txt', '.log']:
                actual_profile_path = str(profile_path_obj.parent)
            elif profile_path_obj.is_file():
                actual_profile_path = str(profile_path_obj.parent)
            else:
                actual_profile_path = credential.profile_path
        else:
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
    
    return True


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
        save_reauth_tokens_to_db(db, result)

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


