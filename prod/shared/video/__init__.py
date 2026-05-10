"""Shared video utilities — composers, subtitles, slideshows.

Reusable across News pipeline, DLE quotes shorts, Sora meme overlay,
and any other module that produces 1920×1080 long-form or 1080×1920
vertical Shorts video.

Modules:
- ``compositor``: ``create_youtube_image`` — 1920×1080 cover with bg + overlay
  + title/author text (1:1 port of Yii ``create_youtube_image`` with brand
  colour configurable per source).
- ``ass_subtitles``: per-word ASS subtitle generator. Word durations are
  distributed evenly across the audio length, last word gets a 2.0s
  reservation. Lena.ttf 140px center-aligned. 1:1 port of Yii ``actionShorts``
  ASS generator (used by all 7 DLE quotes pipelines).
- ``slideshow``: Ken Burns slideshow — N images + 1 audio → 1920×1080 (long)
  or 1080×1920 (shorts). Uses ``zoompan=z='1+0.00012*on'`` (3% zoom over 5s).
  1:1 port of Yii ``makeYoutubeVideoFrom5Images`` / ``makeShortsFrom5Images``.
"""

from shared.video.ass_subtitles import (
    sec2ass,
    generate_per_word_ass,
)
from shared.video.compositor import (
    create_youtube_image,
    BrandColour,
    BRAND_GREEN,
    BRAND_WHITE,
)
from shared.video.slideshow import (
    make_long_slideshow,
    make_shorts_slideshow,
    burn_subtitles,
)

__all__ = [
    "sec2ass",
    "generate_per_word_ass",
    "create_youtube_image",
    "BrandColour",
    "BRAND_GREEN",
    "BRAND_WHITE",
    "make_long_slideshow",
    "make_shorts_slideshow",
    "burn_subtitles",
]
