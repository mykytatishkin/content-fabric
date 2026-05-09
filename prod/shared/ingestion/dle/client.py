"""SQLAlchemy-based DLE client for fetching posts from external MySQL databases.

Some DLE installs ship a `book_id` column on `dle_post` (audiokniga_one,
knigi_audio_biz, club_books_ru, slushat_knigi_com, bazaknig_net) — others do
not (books_online_info, knigi_online_club). We auto-detect this once per
engine and emit a SELECT that matches the schema.
"""

import logging
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from shared.ingestion.dle.xfields_parser import parse_xfields, get_normalized_fields

logger = logging.getLogger(__name__)

_BASE_COLUMNS = "id, title, short_story, full_story, xfields, date, category, alt_name"


class DleClient:
    def __init__(self, dsn: str, source_slug: str):
        self.dsn = dsn
        self.source_slug = source_slug
        self._engine: Engine | None = None
        self._has_book_id: bool | None = None

    def get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.dsn,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine

    def _columns(self) -> str:
        if self._has_book_id is None:
            self._has_book_id = self._detect_book_id()
        return _BASE_COLUMNS + (", book_id" if self._has_book_id else "")

    def _detect_book_id(self) -> bool:
        try:
            with self.get_engine().connect() as conn:
                rows = conn.execute(
                    text("SHOW COLUMNS FROM dle_post LIKE 'book_id'")
                ).fetchall()
                return len(rows) > 0
        except Exception as exc:
            logger.warning("[DLE CLIENT] book_id detection failed for %s: %s",
                           self.source_slug, exc)
            return False

    def fetch_recent_posts(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch recent approved posts from dle_post."""
        logger.info("[DLE CLIENT] Fetching posts from %s. Limit=%d, Offset=%d",
                    self.source_slug, limit, offset)

        query = text(
            f"SELECT {self._columns()} FROM dle_post "
            "WHERE approve = 1 "
            "ORDER BY date DESC LIMIT :limit OFFSET :offset"
        )

        posts: list[dict[str, Any]] = []
        try:
            with self.get_engine().connect() as conn:
                result = conn.execute(query, {"limit": limit, "offset": offset})
                for row in result:
                    post = dict(row._mapping)
                    post["xfields_parsed"] = parse_xfields(post.get("xfields"))
                    post["normalized"] = get_normalized_fields(
                        post["xfields_parsed"], self.source_slug
                    )
                    posts.append(post)
            logger.info("[DLE CLIENT] SUCCESS: Fetched %d posts from %s",
                        len(posts), self.source_slug)
        except Exception as e:
            logger.error("[DLE CLIENT] ERROR fetching posts from %s: %s",
                         self.source_slug, e)

        return posts

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        """Fetch a single post by ID."""
        query = text(
            f"SELECT {self._columns()} FROM dle_post WHERE id = :id"
        )

        try:
            with self.get_engine().connect() as conn:
                result = conn.execute(query, {"id": post_id}).first()
                if result:
                    post = dict(result._mapping)
                    post["xfields_parsed"] = parse_xfields(post["xfields"])
                    post["normalized"] = get_normalized_fields(
                        post["xfields_parsed"], self.source_slug
                    )
                    return post
        except Exception as e:
            logger.error("Failed to fetch post %d from %s: %s",
                         post_id, self.source_slug, e)

        return None
