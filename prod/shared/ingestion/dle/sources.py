"""Per-DLE-source asset URL builders + audio resolvers.

1:1 port of Yii PHP controllers (yii/console/controllers/*Controller.php) and
yii/common/components/MyFunction.php helpers (`imgurl`, `downloadFileffmpeg`).

Why this exists: the public site URLs (audiokniga-one.com, knigi-audio.biz, etc.)
front a Cloudflare "Managed Challenge" wall that plain HTTP clients cannot solve.
PHP never went through the public site for asset fetches — it always used the
unprotected origin CDN directly:
  - https://vvoqhuz9dcid9zx9.redirectto.cc — covers + .pl.txt + MP3 storage
  - https://cdn.my-library.info — covers for books-online / slushat-knigi

Each source uses a *different* path layout (s01 vs s20, derived from book_id vs
xfields['tr_id'] vs xfields['baza_knig_info_id']). The builders below mirror the
exact PHP logic line-for-line.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)

CDN_REDIRECTTO = "https://vvoqhuz9dcid9zx9.redirectto.cc"
CDN_MY_LIBRARY = "https://cdn.my-library.info"

# 1:1 port of MyFunction::downloadFileffmpeg UA (the PHP code uses Chrome 24
# from 2013 which still works against the origin CDN; we use Chrome 120 to
# match the rest of the codebase).
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def imgurl(img_id: int | str) -> str:
    """Port of MyFunction::imgurl — split each digit with '/'.

    Examples: 275374 -> '2/7/5/3/7/4/'; 1 -> '1/'.
    """
    return "".join(c + "/" for c in str(img_id))


def _xf(post: dict[str, Any], *keys: str) -> str | None:
    """First non-empty value across xfields_parsed for any of the given keys."""
    xf = post.get("xfields_parsed") or {}
    for k in keys:
        v = xf.get(k)
        if v not in (None, "", "images/no-cover.jpg"):
            return str(v)
    return None


# ---------- Cover URL builders (return (url, referer) or (None, "")) ----------

def _cover_audiokniga_one_com(post: dict[str, Any]) -> tuple[str | None, str]:
    # PHP Audiokniga_one_com generates the cover from book_id via overlay; for
    # ingestion we just need *some* image. xfields['cover'] usually holds it.
    cover = _xf(post, "cover", "wallpaper")
    if not cover:
        return None, ""
    if cover.startswith(("http://", "https://")):
        return cover, CDN_REDIRECTTO
    return f"{CDN_REDIRECTTO}/{cover.lstrip('/')}", CDN_REDIRECTTO


def _cover_knigi_audio_biz(post: dict[str, Any]) -> tuple[str | None, str]:
    # Same flavour as audiokniga (Unique_audioController.php).
    return _cover_audiokniga_one_com(post)


def _cover_bazaknig_net(post: dict[str, Any]) -> tuple[str | None, str]:
    # PHP: redirectto.cc/s01/{imgurl(baza_knig_info_id)}{xfields['cover']}
    info_id = _xf(post, "baza_knig_info_id")
    cover = _xf(post, "cover")
    if not info_id or not cover:
        return None, ""
    return f"{CDN_REDIRECTTO}/s01/{imgurl(info_id)}{cover}", "https://cdn.bazaknig.net"


def _cover_club_books_ru(post: dict[str, Any]) -> tuple[str | None, str]:
    # PHP: redirectto.cc/s20/{imgurl(tr_id)}{tr_id}.jpg
    tr_id = _xf(post, "tr_id")
    if not tr_id:
        return None, ""
    return f"{CDN_REDIRECTTO}/s20/{imgurl(tr_id)}{tr_id}.jpg", CDN_REDIRECTTO


def _cover_knigi_online_club(post: dict[str, Any]) -> tuple[str | None, str]:
    # Same pattern as club_books_ru.
    return _cover_club_books_ru(post)


def _cover_books_online_info(post: dict[str, Any]) -> tuple[str | None, str]:
    # PHP: cdn.my-library.info/{xfields['wallpaper']}  (wallpaper is a path like books/419369/419369.jpg)
    wallpaper = _xf(post, "wallpaper", "cover")
    if not wallpaper:
        return None, ""
    if wallpaper.startswith(("http://", "https://")):
        return wallpaper, CDN_MY_LIBRARY
    return f"{CDN_MY_LIBRARY}/{wallpaper.lstrip('/')}", CDN_MY_LIBRARY


def _cover_slushat_knigi_com(post: dict[str, Any]) -> tuple[str | None, str]:
    # PHP Slushat_knigi_comController points at cdn.my-library.info but that
    # mirror is dead for new posts (verified 2026-05-09 — all post IDs from
    # 70K range return 404). Real assets live on the public site itself, which
    # is *not* behind Cloudflare's managed challenge (verified — 200 from prod).
    cover = _xf(post, "cover", "wallpaper")
    if not cover:
        return None, ""
    if cover.startswith(("http://", "https://")):
        return cover, "https://slushat-knigi.com/"
    return f"https://slushat-knigi.com/uploads/posts/{cover.lstrip('/')}", "https://slushat-knigi.com/"


COVER_BUILDERS: dict[str, Callable[[dict[str, Any]], tuple[str | None, str]]] = {
    "audiokniga_one_com":  _cover_audiokniga_one_com,
    "knigi_audio_biz":     _cover_knigi_audio_biz,
    "bazaknig_net":         _cover_bazaknig_net,
    "club_books_ru":        _cover_club_books_ru,
    "knigi_online_club":    _cover_knigi_online_club,
    "books_online_info":    _cover_books_online_info,
    "slushat_knigi_com":    _cover_slushat_knigi_com,
}


def build_cover_url(source_slug: str, post: dict[str, Any]) -> tuple[str | None, str]:
    """Return (cover_url, referer) for the given source/post, mirroring PHP."""
    builder = COVER_BUILDERS.get(source_slug)
    if builder is None:
        return None, ""
    return builder(post)


# ---------- Audio playlist resolver (audiokniga_one_com / knigi_audio_biz) ----

# Sources whose audio is stored as a `.pl.txt` JSON playlist on redirectto.cc.
PLAYLIST_SOURCES = {"audiokniga_one_com", "knigi_audio_biz"}


def fetch_playlist_mp3s(book_id: int | str, dest_dir: str) -> list[str] | None:
    """Download `<book_id>.pl.txt` from redirectto.cc, parse JSON, return MP3 URLs.

    1:1 port of Audiokniga_one_comController and Unique_audioController:
        $pl_txt = redirectto.cc/s01/{imgurl(book_id)}{book_id}.pl.txt
        $mp3_arr = MyFunction::getRegexprall_arr('/"file":"(.*?)"\\}/', $text_pl, 1);
    """
    pl_url = f"{CDN_REDIRECTTO}/s01/{imgurl(book_id)}{book_id}.pl.txt"
    pl_path = os.path.join(dest_dir, f"{book_id}.pl.txt")
    headers = dict(DEFAULT_HEADERS)
    headers["Referer"] = CDN_REDIRECTTO
    try:
        r = requests.get(pl_url, headers=headers, timeout=20)
        r.raise_for_status()
        with open(pl_path, "w", encoding="utf-8") as f:
            f.write(r.text)
    except Exception as exc:
        logger.warning("[DLE SOURCES] playlist fetch failed for book_id=%s: %s", book_id, exc)
        return None

    # Match PHP regex `"file":"(.*?)"\}` (note: `}` is part of the literal because
    # JSON entries look like `{"title":"1","file":"<URL>"}`).
    raw_matches = re.findall(r'"file":"(.*?)"\}', r.text)
    # Decode JSON-escaped slashes.
    mp3s = [m.replace("\\/", "/").replace("\\\\", "\\") for m in raw_matches]
    try:
        os.unlink(pl_path)
    except OSError:
        pass
    return mp3s or None
