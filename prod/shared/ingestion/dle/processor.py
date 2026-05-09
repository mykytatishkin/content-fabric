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
from typing import Any, Literal

import requests

from shared.ingestion.dle import sources as dle_sources
from shared.voice.changer import process_voice_change

logger = logging.getLogger(__name__)

# Audio source mode for DLE post processing.
# - "mp3"        — legacy default: download an existing MP3 file (URL/scrape).
# - "tts_openai" — render `full_story`/annotation via shared.tts.openai_tts.
#                  Used by knigi_online_club / books_online_info "TXT-flavour"
#                  posts that ship long-form text rather than a ready audiofile.
AudioSource = Literal["mp3", "tts_openai"]


class DleProcessor:
    """Обрабатывает одну DLE-задачу: скачивание → voice → видео."""

    def __init__(self, work_dir: str = "/tmp/dle_processing",
                 audio_source: AudioSource = "mp3"):
        """
        Args:
            work_dir: scratch directory for intermediate files.
            audio_source: how to obtain source audio.
                "mp3"        (default) — download a pre-existing MP3.
                "tts_openai" — synthesise from `full_story` text via OpenAI TTS,
                               using `shared.tts.source_defaults` for per-slug
                               voice/instructions. Replaces the legacy Yii
                               `actionTts_openai` shell-out.
        """
        self.work_dir = work_dir
        self.audio_source = audio_source
        os.makedirs(self.work_dir, exist_ok=True)

    # ── Public API ───────────────────────────────────────────────

    def process_task(self, task: dict[str, Any]) -> str | None:
        """Возвращает путь к final mp4 или None при ошибке."""
        legacy = self._parse_legacy(task.get("legacy_add_info"))
        normalized = legacy.get("normalized") or {}
        source_slug = legacy.get("dle_source") or ""
        dle_id = legacy.get("dle_post_id")

        logger.info("[DLE PROCESSOR] START task=%s source=%s dle_id=%s audio_source=%s",
                    task.get("id"), source_slug, dle_id, self.audio_source)

        task_dir = os.path.join(self.work_dir, f"task_{task.get('id')}")
        os.makedirs(task_dir, exist_ok=True)

        try:
            # 1. Cover (per-source builder, 1:1 PHP port via sources.py)
            xfields_parsed = legacy.get("xfields_parsed") or {}
            book_id = legacy.get("book_id")

            # Backfill xfields/book_id from the source DLE DB for tasks created
            # before pipeline started persisting them (otherwise per-source URL
            # builders can't run and we'd fall back to the CF-walled public site).
            if (not xfields_parsed or not book_id) and dle_id and source_slug:
                fresh = self._refetch_dle_post(source_slug, int(dle_id))
                if fresh:
                    xfields_parsed = fresh.get("xfields_parsed") or xfields_parsed
                    book_id = fresh.get("book_id") or book_id

            cover_post = {
                "id": task.get("id"),
                "xfields_parsed": xfields_parsed,
                "normalized": normalized,
                "book_id": book_id,
            }
            cover_path = self._fetch_cover(task_dir, source_slug, cover_post)
            # Re-export back into legacy so audio resolver below sees them.
            legacy["xfields_parsed"] = xfields_parsed
            legacy["book_id"] = book_id

            # 2. YouTube background image (1920x1080)
            bg_path = os.path.join(task_dir, "youtube_image.jpg")
            self._create_youtube_image(
                bg_path, cover_path,
                title=normalized.get("book_name") or task.get("title") or "",
                author=normalized.get("author") or "",
            )

            # 3. Audio
            if self.audio_source == "tts_openai":
                audio_path = self._render_tts(task_dir, source_slug, normalized, legacy)
            else:
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

    # Slug → env-var name for the DLE source DSN. Used by `_refetch_dle_post`
    # to backfill xfields/book_id for tasks created before the pipeline started
    # persisting those fields into legacy_add_info.
    _DSN_ENV_BY_SLUG = {
        "knigi_audio_biz":     "DLE_KNIGI_AUDIO_DSN",
        "audiokniga_one_com":  "DLE_AUDIOKNIGA_DSN",
        "club_books_ru":       "DLE_CLUB_BOOKS_DSN",
        "books_online_info":   "DLE_BOOKS_ONLINE_DSN",
        "slushat_knigi_com":   "DLE_SLUSHAT_DSN",
        "knigi_online_club":   "DLE_KNIGI_ONLINE_DSN",
        "bazaknig_net":         "DLE_BAZAKNIG_DSN",
    }

    def _refetch_dle_post(self, source_slug: str, post_id: int) -> dict[str, Any] | None:
        env_var = self._DSN_ENV_BY_SLUG.get(source_slug)
        if not env_var:
            return None
        dsn = os.environ.get(env_var)
        if not dsn:
            return None
        try:
            from shared.ingestion.dle.client import DleClient
            return DleClient(dsn=dsn, source_slug=source_slug).get_post_by_id(post_id)
        except Exception as exc:
            logger.warning("[DLE PROCESSOR] re-fetch failed for %s/%s: %s",
                           source_slug, post_id, exc)
            return None

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

    def _fetch_cover(self, task_dir: str, source_slug: str, post: dict[str, Any]) -> str | None:
        """Build per-source cover URL via `sources.build_cover_url` (1:1 PHP port).

        Falls back to `normalized['cover']` if the per-source builder returned
        nothing — so callers that only have a normalized URL still work.
        """
        url, referer = dle_sources.build_cover_url(source_slug, post)
        if not url:
            normalized = post.get("normalized") or {}
            cover = normalized.get("cover")
            if cover and cover.startswith(("http://", "https://")):
                url, referer = cover, ""
        if not url:
            logger.warning("[DLE PROCESSOR] No cover URL resolvable for source=%s post=%s",
                           source_slug, post.get("id"))
            return None

        out_path = os.path.join(task_dir, "cover.jpg")
        return self._download(url, out_path, timeout=20, referer=referer or None)

    # Real Chrome 120 fingerprint — DLE sites started returning 403 for bare
    # "Mozilla/5.0" on 2026-05-09 (likely Cloudflare/anti-bot challenge). Full
    # browser headers + auto-Referer recover ~100% of cover/audio fetches.
    _BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
    }

    @classmethod
    def _download(cls, url: str, dest: str, timeout: int = 30,
                  referer: str | None = None) -> str | None:
        try:
            headers = dict(cls._BROWSER_HEADERS)
            if referer:
                headers["Referer"] = referer
            else:
                try:
                    from urllib.parse import urlparse as _urlparse
                    _p = _urlparse(url)
                    headers["Referer"] = f"{_p.scheme}://{_p.netloc}/"
                except Exception:
                    pass
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

        Strategy:
          A. audiokniga_one_com / knigi_audio_biz: download `<book_id>.pl.txt`
             playlist from redirectto.cc → fetch each MP3 → concat with ffmpeg.
             Mirrors PHP Audiokniga_one_comController / Unique_audioController.
          B. otherwise: try ready URL in normalized/legacy → xfields fields →
             HTML scrape (last resort).
        """
        # A. Playlist sources (audiokniga + knigi_audio_biz)
        if source_slug in dle_sources.PLAYLIST_SOURCES:
            book_id = legacy.get("book_id")
            if book_id:
                pl_audio = self._fetch_playlist_audio(task_dir, book_id)
                if pl_audio:
                    return pl_audio
                logger.warning("[DLE PROCESSOR] playlist audio failed for source=%s book_id=%s — falling through",
                               source_slug, book_id)

        # B.1 Готовый URL
        url = normalized.get("audio_url") or legacy.get("audio_url")
        if url:
            return self._download(url, os.path.join(task_dir, "source_audio.mp3"), timeout=300)

        # B.2 xfields fields
        xfields = legacy.get("xfields_parsed") or {}
        for key in ("mp3", "audio", "file", "audio_file"):
            v = xfields.get(key)
            if v and isinstance(v, str) and v.startswith(("http://", "https://")):
                return self._download(v, os.path.join(task_dir, "source_audio.mp3"), timeout=300)

        # B.3 HTML scrape (last resort)
        post_url = legacy.get("dle_post_url")
        if post_url:
            mp3_url = self._scrape_mp3_from_page(post_url)
            if mp3_url:
                return self._download(mp3_url, os.path.join(task_dir, "source_audio.mp3"),
                                       timeout=300, referer=post_url)

        logger.warning("[DLE PROCESSOR] Could not resolve audio for source=%s.",
                       source_slug)
        return None

    def _fetch_playlist_audio(self, task_dir: str, book_id: int | str) -> str | None:
        """Download MP3s referenced by `<book_id>.pl.txt` and concat them into one file.

        1:1 with the PHP loop in Audiokniga_one_comController:
          1. download .pl.txt
          2. parse `"file":"<URL>"` matches
          3. download each MP3 (referer=redirectto.cc)
          4. ffmpeg concat → source_audio.mp3
        """
        mp3_urls = dle_sources.fetch_playlist_mp3s(book_id, task_dir)
        if not mp3_urls:
            return None

        local_paths: list[str] = []
        for i, url in enumerate(mp3_urls):
            local = os.path.join(task_dir, f"part_{i:03d}.mp3")
            got = self._download(url, local, timeout=300, referer=dle_sources.CDN_REDIRECTTO)
            if got:
                local_paths.append(local)

        if not local_paths:
            return None
        if len(local_paths) == 1:
            final = os.path.join(task_dir, "source_audio.mp3")
            try:
                os.replace(local_paths[0], final)
            except OSError as exc:
                logger.warning("[DLE PROCESSOR] could not rename single MP3: %s", exc)
                return None
            return final

        # ffmpeg concat using a list file (avoids re-encode by using `-c copy`)
        list_file = os.path.join(task_dir, "concat_list.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for p in local_paths:
                # ffmpeg concat-demuxer needs single-quoted absolute paths
                f.write(f"file '{p}'\n")
        out = os.path.join(task_dir, "source_audio.mp3")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", out,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=1800)
        except subprocess.CalledProcessError as exc:
            logger.error("[DLE PROCESSOR] ffmpeg concat failed: %s", exc.stderr[:1500])
            return None
        if not os.path.isfile(out) or os.path.getsize(out) == 0:
            return None
        # cleanup parts to save disk
        for p in local_paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.unlink(list_file)
        except OSError:
            pass
        return out

    def _render_tts(self, task_dir: str, source_slug: str,
                    normalized: dict[str, Any], legacy: dict[str, Any]) -> str | None:
        """Synthesize source audio from `full_story` (or fallback fields) via OpenAI TTS.

        Used when `audio_source="tts_openai"`. Replaces the legacy Yii
        `actionTts_openai` flow used by 8 DLE controllers; per-slug defaults
        come from `shared.tts.source_defaults`.
        """
        # Lazy-import to avoid hard dependency in the default mp3 path
        try:
            from shared.tts.openai_tts import synthesize
            from shared.tts.source_defaults import get_defaults_for_source
        except ImportError as exc:
            logger.error("[DLE PROCESSOR] tts module unavailable: %s", exc)
            return None

        text = (
            normalized.get("full_story")
            or legacy.get("full_story")
            or normalized.get("annotation")
            or normalized.get("anotation")
            or normalized.get("description")
            or ""
        )
        text = (text or "").strip()
        if not text:
            logger.warning("[DLE PROCESSOR] TTS requested but no text found for source=%s", source_slug)
            return None

        defaults = get_defaults_for_source(source_slug)
        out_path = os.path.join(task_dir, "source_audio.mp3")

        try:
            from pathlib import Path as _P
            synthesize(
                text,
                _P(out_path),
                voice=defaults.get("voice", "nova"),
                language=defaults.get("language"),
                instructions=defaults.get("instructions"),
                response_format="mp3",
            )
            return out_path if os.path.isfile(out_path) and os.path.getsize(out_path) > 0 else None
        except Exception as exc:
            logger.exception("[DLE PROCESSOR] TTS synthesis failed for source=%s: %s",
                             source_slug, exc)
            return None

    @classmethod
    def _scrape_mp3_from_page(cls, url: str) -> str | None:
        """Last resort — скачать HTML и найти .mp3 ссылку regexp'ом."""
        try:
            headers = dict(cls._BROWSER_HEADERS)
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            try:
                from urllib.parse import urlparse as _urlparse
                _p = _urlparse(url)
                headers["Referer"] = f"{_p.scheme}://{_p.netloc}/"
            except Exception:
                pass
            r = requests.get(url, timeout=15, headers=headers)
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
