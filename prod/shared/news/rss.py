"""RBC RSS reader with deduplication.

1:1 port of Yii ``NewsController::actionRbcFirstNews`` — fetch RSS, return
first item not yet processed. Replaces file-based ``rbc_used_links.txt``
with DB table ``news_processed_urls`` (created by migration 005).

Why DB not file: file requires shared FS between Yii server and CFF
workers. DB is the only authoritative state across machines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

import requests

from shared.db.connection import get_engine
from sqlalchemy import text as sql_text

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30
_NS_MEDIA = "http://search.yahoo.com/mrss/"


@dataclass
class NewsItem:
    """RSS-derived news item ready for TTS+slideshow pipeline."""
    title: str
    link: str
    description: str
    fulltext: str
    pub_date: str
    image: str | None


def _is_url_used(link: str) -> bool:
    """Check news_processed_urls (one row per processed RSS link)."""
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                sql_text("SELECT 1 FROM news_processed_urls WHERE link = :l LIMIT 1"),
                {"l": link},
            ).first()
            return row is not None
    except Exception as exc:
        # If table is missing (migration not applied), be conservative — treat
        # as unused but log loudly so operator runs migration 005.
        logger.warning("[NEWS RSS] news_processed_urls check failed: %s "
                       "(run migration 005?) — treating link as unused", exc)
        return False


def _mark_url_used(link: str, source: str = "rbc") -> None:
    """Insert into news_processed_urls. Silent on duplicate (UNIQUE constraint)."""
    try:
        with get_engine().begin() as conn:
            conn.execute(
                sql_text(
                    "INSERT INTO news_processed_urls (link, source, processed_at) "
                    "VALUES (:l, :s, NOW()) "
                    "ON DUPLICATE KEY UPDATE processed_at = NOW()"
                ),
                {"l": link, "s": source},
            )
    except Exception as exc:
        logger.error("[NEWS RSS] mark_url_used failed: %s", exc)


def _extract_image(item: ET.Element) -> str | None:
    """Try enclosure → media:content → None."""
    enc = item.find("enclosure")
    if enc is not None and enc.get("url"):
        return enc.get("url")

    media_content = item.find(f"{{{_NS_MEDIA}}}content")
    if media_content is not None and media_content.get("url"):
        return media_content.get("url")

    return None


def fetch_first_unread(rss_url: str = "https://www.rbc.ua/static/rss/all.ukr.rss.xml") -> NewsItem | None:
    """Fetch RSS, return first item with link not in ``news_processed_urls``.

    Marks the link as used BEFORE returning (to prevent duplicate processing
    if caller crashes between fetch and INSERT into Tasks).

    Returns None if RSS empty / all items already processed / fetch failed.
    """
    try:
        resp = requests.get(rss_url, timeout=_DEFAULT_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0 (CFF news pipeline)"})
        resp.raise_for_status()
        xml_data = resp.content
    except Exception as exc:
        logger.error("[NEWS RSS] fetch failed: %s", exc)
        return None

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        logger.error("[NEWS RSS] parse failed: %s", exc)
        return None

    channel = root.find("channel")
    if channel is None:
        logger.warning("[NEWS RSS] no <channel>")
        return None

    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        if not link:
            continue

        if _is_url_used(link):
            continue

        title = (item.findtext("title") or "").strip()
        description_raw = (item.findtext("description") or "").strip()
        # RBC uses non-namespaced <fulltext> tag
        fulltext_raw = (item.findtext("fulltext") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        # Strip HTML tags from description/fulltext
        description = _strip_html(description_raw)
        fulltext = _strip_html(fulltext_raw)

        image = _extract_image(item)

        # Mark BEFORE return (atomic — won't double-process even on crash)
        _mark_url_used(link, source="rbc")

        return NewsItem(
            title=title,
            link=link,
            description=description,
            fulltext=fulltext,
            pub_date=pub_date,
            image=image,
        )

    logger.info("[NEWS RSS] no new items in feed")
    return None


def _strip_html(s: str) -> str:
    """Cheap HTML strip — RSS rarely has nested tags."""
    import re
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&[a-z]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()
