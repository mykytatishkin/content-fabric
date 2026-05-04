"""Parser for DLE xfields format (key|value||key|value)."""

import re
from typing import Any


def parse_xfields(xfields_str: str | None) -> dict[str, str]:
    """Parse DLE xfields string into a dictionary.
    
    Format: key|value||key|value
    """
    if not xfields_str:
        return {}
    
    result = {}
    # Split by || first
    parts = xfields_str.split("||")
    for part in parts:
        if "|" in part:
            key, value = part.split("|", 1)
            result[key.strip()] = value.strip()
            
    return result


def get_normalized_fields(xfields: dict[str, str], source_slug: str) -> dict[str, Any]:
    """Normalize xfields across different DLE sources.
    
    Handles differences like 'author' vs 'avtor', 'performer' vs 'chtec', etc.
    """
    normalized = {
        "book_name": xfields.get("namebook"),
        "author": xfields.get("author") or xfields.get("avtor"),
        "cover": xfields.get("cover") or xfields.get("wallpaper") or xfields.get("tr_cover"),
        "narrator": xfields.get("performer") or xfields.get("chtec"),
        "duration": xfields.get("time"),
        "external_id": xfields.get("tr_id") or xfields.get("baza_knig_info_id"),
        "page_count": xfields.get("tr_cnt_p"),
    }
    
    # Handle cover path format differences
    if normalized["cover"]:
        # audiokniga and slushat use 'books/ID/ID.jpg'
        # others might use just 'filename.jpg'
        pass

    return normalized
