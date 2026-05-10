"""News pipeline — RBC RSS → 5 SerpAPI images → TTS → Ken Burns slideshow.

Ports Yii ``NewsController`` (1049 lines) to Python:
- ``rss``: RBC.ua RSS reader with deduplication via ``news_processed_urls``
  table (replaces ``rbc_used_links.txt``).
- ``images``: SerpAPI Google Images search (filter width >= 1200, jpg only).
- ``srt_aligner``: forced text-audio alignment via Whisper word-timestamps
  (replaces opaque ``make_srt.py``).
- ``cleaner``: text cleaning (remove ``Читайте також:``, URLs, etc).
- ``video``: orchestration — pulls in shared.video.slideshow + shared.tts.

Endpoints expose:
    fetch_first_unread(rss_url) -> NewsItem | None
    search_images(query, count=5) -> list[str]
    clean_for_tts(text) -> str
    align_subtitles(audio_path, text, output_srt) -> bool
"""

from shared.news.cleaner import clean_for_tts, prepare_text_file
from shared.news.images import search_images
from shared.news.rss import fetch_first_unread, NewsItem
from shared.news.srt_aligner import align_subtitles

__all__ = [
    "fetch_first_unread",
    "NewsItem",
    "search_images",
    "clean_for_tts",
    "prepare_text_file",
    "align_subtitles",
]
