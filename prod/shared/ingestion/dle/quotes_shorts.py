"""DLE Quotes Shorts pipeline — 1 цитата → 1080×1920 short з ASS-субтитрами.

1:1 порт всіх 7 Yii ``actionShorts`` (Audiokniga, Bazaknig, Books_online_info,
Club_books_ru, Knigi_online_club, Slushat_knigi_com, Unique_audio).

Yii flow:
    1. Read first line of `quotes.txt`, remove it from file
    2. Pick random bg image from backgrounds/*.{jpg,jpeg,png}
    3. Pick random bg_music from bg_music/*.mp3
    4. Random voice (4 variants: male/fable, male/echo, female/alloy, female/shimmer)
    5. Random style (14 of 15, no 'whisper')
    6. TTS → audio_tts_1.mp3 → normalize to 48kHz stereo, volume +1.4
    7. Generate ASS per-word subtitles (Lena.ttf 140px, center, Alignment=5)
    8. ffmpeg merge: bg image looped (30fps) + tts_wav + bg_music (volume 0.35)
       + ass overlay → 1080×1920 mp4 with duration = audio_duration
    9. INSERT into `tasks` queue (status=0, scheduled at +N hours)

Per-source video metadata templates are defined in module constants.
"""

from __future__ import annotations

import logging
import os
import random
import shlex
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shared.tts.openai_tts import synthesize as tts_synthesize, map_language_to_voice
from shared.video.ass_subtitles import generate_per_word_ass

logger = logging.getLogger(__name__)


# Yii voice variants — 4 of 11 available OpenAI voices (legacy choice).
# nova/onyx not used in DLE shorts despite being available.
_VOICE_VARIANTS = [
    {"gender": "male",   "voice": "fable"},
    {"gender": "male",   "voice": "echo"},
    {"gender": "female", "voice": "alloy"},
    {"gender": "female", "voice": "shimmer"},
]

# 14 of 15 styles (omit 'whisper' — too quiet for shorts).
# Per OpenAI gpt-4o-mini-tts, instructions can guide vocal style.
_STYLES = [
    "fairytale", "serious", "emotional", "joyful", "calm",
    "mysterious", "dramatic", "storytelling", "sad", "romantic",
    "strict", "robotic", "motivational", "news",
]

_STYLE_INSTRUCTIONS = {
    "fairytale": "розповідай як чарівну казку, з легким натхненням і теплою інтонацією",
    "serious": "серйозним, впевненим голосом, як диктор телебачення",
    "emotional": "емоційно, з глибокими почуттями та виразною інтонацією",
    "joyful": "радісно, із посмішкою в голосі, ніби вітаєш з днем народження",
    "calm": "спокійно, мʼяко, як у медитації чи перед сном",
    "mysterious": "таємничо, трохи повільно, з ефектом інтриги, як у детективі",
    "dramatic": "з високим напруженням, як актор у театрі під час кульмінації",
    "storytelling": "живо і виразно, як захоплений оповідач історії біля багаття",
    "sad": "сумно, з нотками жалю та співчуття",
    "romantic": "ніжно, з інтимною інтонацією, як в любовному листі",
    "strict": "строго і формально, як викладач або чиновник",
    "robotic": "механічно, беземоційно, як штучний інтелект",
    "motivational": "натхненно, підбадьорливо, як тренер або коуч",
    "news": "інформативно, нейтрально, як ведучий новин",
}

# Per-source description templates (1:1 from Yii)
_SITE_TEMPLATES = {
    "audiokniga_one_com": {
        "site_name": "audiokniga-one.com",
        "url": "https://audiokniga-one.com/",
        "description_intro": "Больше аудиокниг для чтения онлайн на сайте audiokniga-one.com",
        "keywords": "цитаты, книги онлайн, аудиокниги бесплатно, аудио книги",
        "post_comment": "Слушайте полные версии аудиокниг здесь: https://audiokniga-one.com/ — наслаждайтесь лучшими аудиокнигами онлайн без регистрации",
    },
    "bazaknig_net": {
        "site_name": "bazaknig.net",
        "url": "https://bazaknig.net/",
        "description_intro": "Больше книг для чтения онлайн на сайте bazaknig.net",
        "keywords": "цитаты, книги онлайн, бесплатно, книги",
        "post_comment": "Читайте полные версии книг здесь: https://bazaknig.net/ — наслаждайтесь лучшими книгами онлайн без регистрации",
    },
    "books_online_info": {
        "site_name": "books-online.info",
        "url": "https://books-online.info/",
        "description_intro": "Больше книг для чтения онлайн на сайте books-online.info",
        "keywords": "цитаты, книги онлайн, бесплатно, книги",
        "post_comment": "Читайте полные версии книг здесь: https://books-online.info/ — наслаждайтесь лучшими книгами онлайн без регистрации",
    },
    "club_books_ru": {
        "site_name": "club-books.ru",
        "url": "https://club-books.ru/",
        "description_intro": "Больше аудиокниг для чтения онлайн на сайте club-books.ru",
        "keywords": "цитаты, книги онлайн, аудиокниги бесплатно, аудио книги",
        "post_comment": "Слушайте полные версии аудиокниг здесь: https://club-books.ru/ — наслаждайтесь лучшими аудиокнигами онлайн без регистрации",
    },
    "knigi_online_club": {
        "site_name": "knigi-online.club",
        "url": "https://knigi-online.club/",
        "description_intro": "Больше книг для чтения онлайн на сайте knigi-online.club",
        "keywords": "цитаты, книги онлайн, бесплатно, книги",
        "post_comment": "Читайте полные версии книг здесь: https://knigi-online.club/ — наслаждайтесь лучшими книгами онлайн без регистрации",
    },
    "slushat_knigi_com": {
        "site_name": "slushat-knigi.com",
        "url": "https://slushat-knigi.com/",
        "description_intro": "Больше книг для чтения онлайн на сайте slushat-knigi.com",
        "keywords": "цитаты, книги онлайн, бесплатно, книги",
        "post_comment": "Читайте полные версии книг здесь: https://slushat-knigi.com/ — наслаждайтесь лучшими книгами онлайн без регистрации",
    },
    "knigi_audio_biz": {
        "site_name": "knigi-audio.biz",
        "url": "https://knigi-audio.biz/",
        "description_intro": "Больше увлекательных книг для чтения онлайн ищите на сайте knigi-audio.biz",
        "keywords": "цитаты, книги онлайн, читать бесплатно, современная литература",
        "post_comment": "Слушайте полные версии аудиокниг здесь: https://knigi-audio.biz/ — наслаждайтесь лучшими аудиокнигами онлайн без регистрации",
    },
}


def _pick_random_file(directory: str, exts: tuple[str, ...]) -> str | None:
    """Pick random file from directory matching any of `exts`."""
    if not os.path.isdir(directory):
        return None
    files = []
    for ext in exts:
        for f in Path(directory).glob(f"*{ext}"):
            if f.is_file():
                files.append(str(f))
    return random.choice(files) if files else None


def _pop_first_quote(quotes_file: str) -> str | None:
    """Read first non-empty line, write back without it. Returns the line or None."""
    if not os.path.isfile(quotes_file):
        return None
    with open(quotes_file, encoding="utf-8") as f:
        lines = [ln.rstrip("\r\n") for ln in f if ln.strip()]
    if not lines:
        return None
    first = lines[0]
    with open(quotes_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines[1:]))
        if len(lines) > 1:
            f.write("\n")
    return first


def _normalize_audio(input_mp3: str, output_wav: str,
                     volume: float = 1.4, sample_rate: int = 48000) -> bool:
    """Normalize TTS to 48 kHz stereo WAV with volume boost.

    1:1 порт Yii ASS shorts:
      ffmpeg -y -i {audio} -ac 2 -ar 48000 -af "volume=1.4" -c:a pcm_s16le {wav}
    """
    cmd = ["ffmpeg", "-y", "-i", input_mp3,
           "-ac", "2", "-ar", str(sample_rate),
           "-af", f"volume={volume}",
           "-c:a", "pcm_s16le", output_wav]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return os.path.isfile(output_wav)
    except subprocess.CalledProcessError as e:
        logger.error("[QUOTES] normalize failed: %s", e.stderr[-300:])
        return False


def _ffprobe_duration(audio_path: str) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", audio_path],
            text=True
        ).strip()
        return float(out)
    except Exception:
        return 0.0


def _compose_short(
    bg_image: str,
    tts_wav: str,
    bg_music: str,
    ass_path: str,
    output_mp4: str,
    audio_duration: float,
) -> bool:
    """Compose 1080×1920 short via ffmpeg. 1:1 port of Yii actionShorts ffmpeg block.

    Filter graph:
      [2:a]atrim=0:DUR,asetpts=N/SR/TB,volume=0.35[a2];
      [1:a][a2]amix=inputs=2:duration=shortest:dropout_transition=0[aout]
    """
    dur = max(0.01, audio_duration)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}",
        "-i", bg_image,
        "-i", tts_wav,
        "-i", bg_music,
        "-filter_complex",
        f"[2:a]atrim=0:{dur:.3f},asetpts=N/SR/TB,volume=0.35[a2];"
        f"[1:a][a2]amix=inputs=2:duration=shortest:dropout_transition=0[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_mp4,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("[QUOTES] compose failed (%d): %s",
                         result.returncode, result.stderr[-500:])
            return False
        return os.path.isfile(output_mp4)
    except Exception as exc:
        logger.exception("[QUOTES] compose crashed: %s", exc)
        return False


def process_quote_short(
    *,
    source_slug: str,
    quotes_file: str,
    backgrounds_dir: str,
    bg_music_dir: str,
    output_dir: str,
    language: str = "ru",
) -> dict[str, Any] | None:
    """Run the full DLE quotes shorts pipeline for ONE quote.

    Returns dict with task metadata for INSERT into Tasks queue, or None on fail.

    Steps:
        1. pop first quote from quotes_file
        2. random bg image, bg_music, voice variant, style
        3. TTS → mp3 → normalize to 48kHz stereo wav
        4. generate ASS per-word subtitles
        5. compose final 1080×1920 mp4
        6. return task metadata (caller does Tasks INSERT)
    """
    template = _SITE_TEMPLATES.get(source_slug)
    if not template:
        logger.error("[QUOTES] unknown source_slug: %s", source_slug)
        return None

    # 1. Pop quote
    quote = _pop_first_quote(quotes_file)
    if not quote:
        logger.info("[QUOTES] no quotes left for %s", source_slug)
        return None
    logger.info("[QUOTES] processing quote (len=%d): %s...", len(quote), quote[:80])

    # 2. Random resources
    bg_image = _pick_random_file(backgrounds_dir, (".jpg", ".jpeg", ".png"))
    if not bg_image:
        logger.error("[QUOTES] no backgrounds in %s", backgrounds_dir)
        return None
    bg_music = _pick_random_file(bg_music_dir, (".mp3",))
    if not bg_music:
        logger.error("[QUOTES] no bg_music in %s", bg_music_dir)
        return None

    voice_choice = random.choice(_VOICE_VARIANTS)
    style = random.choice(_STYLES)
    logger.info("[QUOTES] voice=%s/%s style=%s bg=%s music=%s",
                voice_choice["gender"], voice_choice["voice"], style,
                os.path.basename(bg_image), os.path.basename(bg_music))

    os.makedirs(output_dir, exist_ok=True)

    # 3. TTS
    audio_mp3 = os.path.join(output_dir, "audio_tts.mp3")
    try:
        tts_synthesize(
            quote, audio_mp3,
            voice=voice_choice["voice"],
            language=language,
            instructions=_STYLE_INSTRUCTIONS.get(style),
        )
    except Exception as exc:
        logger.exception("[QUOTES] TTS failed: %s", exc)
        return None

    if not os.path.isfile(audio_mp3) or os.path.getsize(audio_mp3) < 1024:
        logger.error("[QUOTES] TTS produced empty file")
        return None

    # 4. Normalize → tts_norm.wav
    tts_wav = os.path.join(output_dir, "tts_norm.wav")
    if not _normalize_audio(audio_mp3, tts_wav):
        return None

    audio_duration = _ffprobe_duration(tts_wav)
    if audio_duration <= 0:
        logger.error("[QUOTES] zero audio duration")
        return None
    logger.info("[QUOTES] audio_duration=%.2fs", audio_duration)

    # 5. ASS per-word subtitles
    ass_content = generate_per_word_ass(
        quote, audio_duration,
        font_family="Lena", font_size=140,
    )
    ass_path = os.path.join(output_dir, "text.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    # 6. Compose final mp4
    output_mp4 = os.path.join(output_dir, "shorts.mp4")
    if not _compose_short(bg_image, tts_wav, bg_music, ass_path,
                          output_mp4, audio_duration):
        return None

    # 7. Build task metadata (caller does INSERT)
    description = (
        f"{template['description_intro']}: \n                    👉 {template['url']}\n\n"
        f"        Откройте для себя новые истории и слушайте бесплатно прямо в браузере! {quote}"
    )
    return {
        "source_slug": source_slug,
        "quote": quote,
        "title": quote[:255].strip(),  # strip_tags noop — quote is plain text
        "description": description,
        "keywords": template["keywords"],
        "post_comment": template["post_comment"],
        "att_file_path": output_mp4,
        "media_type": "shorts",
        "voice": voice_choice["voice"],
        "style": style,
        "audio_duration_sec": audio_duration,
    }
