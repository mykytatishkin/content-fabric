"""SQLAlchemy-based DLE client for fetching posts from external MySQL databases."""

import logging
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from shared.ingestion.dle.xfields_parser import parse_xfields, get_normalized_fields

logger = logging.getLogger(__name__)


class DleClient:
    def __init__(self, dsn: str, source_slug: str):
        self.dsn = dsn
        self.source_slug = source_slug
        self._engine: Engine | None = None

    def get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.dsn,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine

    def fetch_recent_posts(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch recent approved posts from dle_post."""
        query = text("""
            SELECT id, title, short_story, full_story, xfields, date, category, alt_name
            FROM dle_post
            WHERE approve = 1
            ORDER BY date DESC
            LIMIT :limit OFFSET :offset
        """)
        
        posts = []
        try:
            with self.get_engine().connect() as conn:
                result = conn.execute(query, {"limit": limit, "offset": offset})
                for row in result:
                    post = dict(row._mapping)
                    post["xfields_parsed"] = parse_xfields(post["xfields"])
                    post["normalized"] = get_normalized_fields(post["xfields_parsed"], self.source_slug)
                    posts.append(post)
        except Exception as e:
            logger.error("Failed to fetch posts from %s: %s", self.source_slug, e)
            
        return posts

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        """Fetch a single post by ID."""
        query = text("""
            SELECT id, title, short_story, full_story, xfields, date, category, alt_name
            FROM dle_post
            WHERE id = :id
        """)
        
        try:
            with self.get_engine().connect() as conn:
                result = conn.execute(query, {"id": post_id}).first()
                if result:
                    post = dict(result._mapping)
                    post["xfields_parsed"] = parse_xfields(post["xfields"])
                    post["normalized"] = get_normalized_fields(post["xfields_parsed"], self.source_slug)
                    return post
        except Exception as e:
            logger.error("Failed to fetch post %d from %s: %s", post_id, self.source_slug, e)
            
        return None
