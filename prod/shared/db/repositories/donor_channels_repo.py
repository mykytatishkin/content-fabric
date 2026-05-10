"""Repository for donor_channel_configs + donor_channel_sources tables.

Replaces Yii ``arr_data`` static config from ``Shorts_from_videoController``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text as sql_text

from shared.db.connection import get_engine

logger = logging.getLogger(__name__)


@dataclass
class DonorChannelConfig:
    """Per-target-channel donor configuration."""
    id: int
    channel_id: int
    legacy_yii_acc_id: int | None
    language: str
    target_handle: str
    target_name: str
    keywords: str
    enabled: bool


@dataclass
class DonorChannelSource:
    """One donor YouTube channel feeding into a config."""
    id: int
    config_id: int
    yt_channel_id: str
    yt_handle: str
    enabled: bool


def get_config_by_channel(channel_id: int) -> DonorChannelConfig | None:
    """Lookup config by target platform_channels.id (or legacy_yii_acc_id)."""
    with get_engine().begin() as conn:
        row = conn.execute(
            sql_text("""
                SELECT id, channel_id, legacy_yii_acc_id, language,
                       target_handle, target_name, keywords, enabled
                FROM donor_channel_configs
                WHERE channel_id = :cid AND enabled = 1
                LIMIT 1
            """),
            {"cid": channel_id},
        ).mappings().first()
    if not row:
        return None
    return DonorChannelConfig(
        id=row["id"],
        channel_id=row["channel_id"],
        legacy_yii_acc_id=row["legacy_yii_acc_id"],
        language=row["language"],
        target_handle=row["target_handle"],
        target_name=row["target_name"],
        keywords=row["keywords"],
        enabled=bool(row["enabled"]),
    )


def get_config_by_legacy_acc(legacy_yii_acc_id: int) -> DonorChannelConfig | None:
    """Lookup by legacy Yii youtube_account.id (28/31/34)."""
    with get_engine().begin() as conn:
        row = conn.execute(
            sql_text("""
                SELECT id, channel_id, legacy_yii_acc_id, language,
                       target_handle, target_name, keywords, enabled
                FROM donor_channel_configs
                WHERE legacy_yii_acc_id = :lid
                LIMIT 1
            """),
            {"lid": legacy_yii_acc_id},
        ).mappings().first()
    if not row:
        return None
    return DonorChannelConfig(
        id=row["id"],
        channel_id=row["channel_id"],
        legacy_yii_acc_id=row["legacy_yii_acc_id"],
        language=row["language"],
        target_handle=row["target_handle"],
        target_name=row["target_name"],
        keywords=row["keywords"],
        enabled=bool(row["enabled"]),
    )


def get_sources_for_config(config_id: int) -> list[DonorChannelSource]:
    """List all enabled donor sources for a config."""
    with get_engine().begin() as conn:
        rows = conn.execute(
            sql_text("""
                SELECT id, config_id, yt_channel_id, yt_handle, enabled
                FROM donor_channel_sources
                WHERE config_id = :cid AND enabled = 1
                ORDER BY id
            """),
            {"cid": config_id},
        ).mappings().all()
    return [
        DonorChannelSource(
            id=r["id"], config_id=r["config_id"],
            yt_channel_id=r["yt_channel_id"], yt_handle=r["yt_handle"],
            enabled=bool(r["enabled"]),
        )
        for r in rows
    ]


def list_all_enabled_configs() -> list[DonorChannelConfig]:
    """All enabled donor configs — for periodic shorts_from_donors batch."""
    with get_engine().begin() as conn:
        rows = conn.execute(
            sql_text("""
                SELECT id, channel_id, legacy_yii_acc_id, language,
                       target_handle, target_name, keywords, enabled
                FROM donor_channel_configs
                WHERE enabled = 1
                ORDER BY id
            """),
        ).mappings().all()
    return [
        DonorChannelConfig(
            id=r["id"], channel_id=r["channel_id"],
            legacy_yii_acc_id=r["legacy_yii_acc_id"],
            language=r["language"], target_handle=r["target_handle"],
            target_name=r["target_name"], keywords=r["keywords"],
            enabled=bool(r["enabled"]),
        )
        for r in rows
    ]
