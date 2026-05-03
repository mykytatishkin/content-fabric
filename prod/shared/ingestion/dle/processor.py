"""DLE post processor: download cover & MP3, voice-change, assemble final video.

Replaces logic from Yii Audiokniga_one_comController::actionUpload_to_youtube + analogues.

Pipeline (simplified MVP):
    1. Загрузить обложку (HTTP GET) → task_dir/cover.jpg
    2. Сгенерировать YouTube background image (1920x1080) с обложкой по центру
       + текст book_name + author (через PIL).
    3. Найти/собрать MP3 (см. _resolve_audio_url; для большинства DLE — это
       поле в xfields с прямой ссылкой или playlist.txt в специфичном формате).
    4. Прогнать voice change через CFF voice module.
    5. ffmpeg склеить статичное изображение + аудио → final mp4.
    6. Вернуть путь к final mp4.

Если на каком-то шаге не удалось — возвращает None, ошибка в logger + Telegram.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Any

import requests

from shared.voice.changer import process_voice_change

logger = logging.getLogger(__name__)


# Cover URL templates per source. Если cover в xfields — это просто имя файла,
# нужно собрать полный URL.
COVER_URL_TEMPLATES = {
    "knigi_audio_biz":     "https://knigi-audio.biz/uploads/posts/{cover}",
    "audiokniga_one_com":  "https://audiokniga-one.com/uploads/{cover}",
    "club_books_ru":       "https://club-books.ru/uploads/posts/{cover}",
    "books_online_info":   "https://books-online.info/uploads/{cover}",
    "slushat_knigi_com":   "https://slushat-knigi.com/uploads/{cover}",
    "knigi_online_club":   "https://knigi-online.club/uploads/posts/{cover}",
    "bazaknig_net":        "https://bazaknig.net/uploads/posts/{cover}",
}


class DleProcessor:
    """Обрабатывает одну DLE-задачу: скачивание → voice → видео."""

    def __init__(self, work_dir: str = "/tmp/dle_processing"):
        self.work_dir = work_dir
        os.makedirs(self.work_dir, exist_ok=True)

    # ── Public API ───────────────────────────────────────────────

    def process_task(self, task: dict[str, Any]) -> str | None:
        """Возвращает путь к final mp4 или None при ошибке."""
        legacy = self._parse_legacy(task.get("legacy_add_info"))
        normalized = legacy.get("normalized") or {}
        source_slug = legacy.get("dle_source") or ""
        dle_id = legacy.get("dle_post_id")

        logger.info("[DLE PROCESSOR] START task=%s source=%s dle_id=%s",
                    task.get("id"), source_slug, dle_id)

        task_dir = os.path.join(self.work_dir, f"task_{task.get('id')}")
        os.makedirs(task_dir, exist_ok=True)

        try:
            # 1. Cover
            cover_path = self._fetch_cover(task_dir, source_slug, normalized.get("cover"))

            # 2. YouTube background image (1920x1080)
            bg_path = os.path.join(task_dir, "youtube_image.jpg")
            self._create_youtube_image(
                bg_path, cover_path,
                title=normalized.get("book_name") or task.get("title") or "",
                author=normalized.get("author") or "",
            )

            # 3. Audio
            audio_path = self._resolve_audio(task_dir, source_slug, normalized, legacy)
            if not audio_path:
                raise RuntimeError("Failed to resolve audio source")

            # 4. Voice change
            processed_audio = os.path.join(task_dir, "processed_audio.mp3")
            try:
                process_voice_change(
                    source_file_path=audio_path,
                    output_file_path=processed_audio,
                    preserve_background=True,
                )
            except Exception:
                logger.exception("[DLE PROCESSOR] voice change failed for task=%s — fallback to original audio", task.get("id"))
                processed_audio = audio_path  # fallback: используем оригинал

            # 5. Final video
            final_video = os.path.join(task_dir, "final_video.mp4")
            if not self._assemble_video(bg_path, processed_audio, final_video):
                raise RuntimeError("ffmpeg video assembly failed")

            logger.info("[DLE PROCESSOR] DONE task=%s → %s", task.get("id"), final_video)
            return final_video

        except Exception as exc:
            logger.exception("[DLE PROCESSOR] FAIL task=%s: %s", task.get("id"), exc)
            return None

    # ── Internals ────────────────────────────────────────────────

    @staticmethod
    def _parse_legacy(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                import json
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    def _fetch_cover(self, task_dir: str, source_slug: str, cover: str | None) -> str | None:
        if not cover:
            return None
        # Если уже полный URL — берём как есть
        if cover.startswith(("http://", "https://")):
            url = cover
        else:
            tmpl = COVER_URL_TEMPLATES.get(source_slug)
            if not tmpl:
                logger.warning("[DLE PROCESSOR] No cover URL template for source=%s", source_slug)
                return None
            url = tmpl.format(cover=cover.lstrip("/"))

        out_path = os.path.join(task_dir, "cover.jpg")
        return self._download(url, out_path, timeout=20)

    @staticmethod
    def _download(url: str, dest: str, timeout: int = 30,
                  referer: str | None = None) -> str | None:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            if referer:
                headers["Referer"] = referer
            r = requests.get(url, stream=True, timeout=timeout, headers=headers)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
            return dest
        except Exception as exc:
            logger.warning("[DLE PROCESSOR] Download failed %s: %s", url, exc)
            return None

    def _create_youtube_image(self, output_path: str, cover_path: str | None,
                              title: str, author: str) -> bool:
        """Генерация 1920x1080 фона: чёрный + cover по центру + текст title/author.

        Использует PIL. Если PIL не доступен — fallback на копию cover'а
        (не лучший вариант, но видео всё равно соберётся).
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("[DLE PROCESSOR] PIL not available, falling back to copy")
            if cover_path and os.path.isfile(cover_path):
                import shutil
                shutil.copy(cover_path, output_path)
                return True
            # Полный фолбэк — пустой 1920x1080 чёрный JPEG через ffmpeg
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=1920x1080:d=1",
                    "-vframes", "1", output_path,
                ], check=True, capture_output=True)
                return True
            except Exception:
                return False

        # Создание изображения через PIL
        W, H = 1920, 1080
        img = Image.new("RGB", (W, H), (15, 15, 20))
        draw = ImageDraw.Draw(img)

        # Cover в центре (max 720x720, сохраняя пропорции)
        if cover_path and os.path.isfile(cover_path):
            try:
                cover = Image.open(cover_path).convert("RGB")
                cover.thumbnail((720, 720), Image.LANCZOS)
                cw, ch = cover.size
                cx = (W - cw) // 2
                cy = (H - ch) // 2 - 40
                img.paste(cover, (cx, cy))
            except Exception as exc:
                logger.warning("[DLE PROCESSOR] Cover paste failed: %s", exc)

        # Текст title + author под обложкой
        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_title = ImageFont.truetype(font_path, 56) if os.path.isfile(font_path) else ImageFont.load_default()
            font_author = ImageFont.truetype(font_path, 38) if os.path.isfile(font_path) else ImageFont.load_default()
        except Exception:
            font_title = ImageFont.load_default()
            font_author = ImageFont.load_default()

        title_short = title[:80]
        author_short = author[:60]

        # Title
        draw.text((W // 2, H - 200), title_short, fill=(245, 245, 247),
                  font=font_title, anchor="mm")
        # Author
        if author_short:
            draw.text((W // 2, H - 130), author_short, fill=(180, 180, 190),
                      font=font_author, anchor="mm")

        img.save(output_path, "JPEG", quality=92)
        return True

    def _resolve_audio(self, task_dir: str, source_slug: str,
                       normalized: dict[str, Any], legacy: dict[str, Any]) -> str | None:
        """Найти и скачать MP3 для книги.

        Стратегия по источникам:
        - Yii использует разные форматы хранения: m3u8 playlist, JSON {file: ...},
          или прямую ссылку в xfields. Для MVP — три попытки:
          1. Готовый URL в normalized.audio_url или legacy.audio_url
          2. mp3 в xfields_parsed (mp3, audio, file)
          3. NotImplemented для конкретного источника — TODO для следующих итераций
        """
        # 1. Готовый URL
        url = normalized.get("audio_url") or legacy.get("audio_url")
        if url:
            return self._download(url, os.path.join(task_dir, "source_audio.mp3"), timeout=300)

        # 2. xfields fields
        xfields = legacy.get("xfields_parsed") or {}
        for key in ("mp3", "audio", "file", "audio_file"):
            v = xfields.get(key)
            if v and isinstance(v, str) and v.startswith(("http://", "https://")):
                return self._download(v, os.path.join(task_dir, "source_audio.mp3"), timeout=300)

        # 3. Не нашли — попробовать найти на странице поста (HTML scrape)
        post_url = legacy.get("dle_post_url")
        if post_url:
            mp3_url = self._scrape_mp3_from_page(post_url)
            if mp3_url:
                return self._download(mp3_url, os.path.join(task_dir, "source_audio.mp3"),
                                       timeout=300, referer=post_url)

        logger.warning("[DLE PROCESSOR] Could not resolve audio for source=%s. "
                       "Add specific logic in _resolve_audio_for_source_<slug>().", source_slug)
        return None

    @staticmethod
    def _scrape_mp3_from_page(url: str) -> str | None:
        """Last resort — скачать HTML и найти .mp3 ссылку regexp'ом."""
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            html = r.text
            # Найти первую mp3 ссылку
            m = re.search(r'https?://[^\s"\']+\.mp3', html)
            return m.group(0) if m else None
        except Exception as exc:
            logger.warning("[DLE PROCESSOR] HTML scrape failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _audio_duration(audio_path: str) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, timeout=30,
            )
            return float(r.stdout.strip()) if r.stdout.strip() else 300.0
        except Exception:
            return 300.0

    def _assemble_video(self, image_path: str, audio_path: str, output_path: str) -> bool:
        duration = self._audio_duration(audio_path)
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1920:1080",
            "-t", f"{duration:.2f}",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3600)
            return os.path.isfile(output_path) and os.path.getsize(output_path) > 0
        except subprocess.CalledProcessError as exc:
            logger.error("[DLE PROCESSOR] ffmpeg assembly failed: %s", exc.stderr[:1500])
            return False
