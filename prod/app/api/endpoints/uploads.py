"""File upload endpoints — accepts video/thumbnail uploads, returns server paths."""

import os
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user
from app.core.audit import log as audit_log

logger = logging.getLogger(__name__)
router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/opt/content-fabric/uploads"))

ALLOWED_VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_VIDEO_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _validate_extension(filename: str, allowed: set[str]) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(allowed))}",
        )
    return ext


@router.post("/video", status_code=status.HTTP_201_CREATED)
@_limiter.limit("10/minute")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a video file. Returns the server path for use in task creation."""
    ext = _validate_extension(file.filename or "video.mp4", ALLOWED_VIDEO_EXT)
    dest_dir = UPLOAD_DIR / "videos"
    _ensure_dir(dest_dir)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / unique_name

    size = 0
    with open(dest_path, "wb") as f:
        while chunk := await file.read(8 * 1024 * 1024):  # 8MB chunks
            size += len(chunk)
            if size > MAX_VIDEO_SIZE:
                f.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Video file too large (max 10 GB)")
            f.write(chunk)

    logger.info("Uploaded video: %s (%d MB)", dest_path, size // (1024 * 1024))
    audit_log("upload.video", actor_id=user.get("id"),
              metadata={"filename": file.filename, "size_mb": round(size / (1024 * 1024), 2), "path": str(dest_path)})

    return {
        "path": str(dest_path),
        "filename": file.filename,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
    }


@router.post("/thumbnail", status_code=status.HTTP_201_CREATED)
@_limiter.limit("20/minute")
async def upload_thumbnail(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a thumbnail image. Returns the server path for use in task creation."""
    ext = _validate_extension(file.filename or "thumb.jpg", ALLOWED_IMAGE_EXT)
    dest_dir = UPLOAD_DIR / "thumbnails"
    _ensure_dir(dest_dir)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / unique_name

    size = 0
    with open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            size += len(chunk)
            if size > MAX_IMAGE_SIZE:
                f.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Thumbnail too large (max 50 MB)")
            f.write(chunk)

    logger.info("Uploaded thumbnail: %s (%d KB)", dest_path, size // 1024)
    audit_log("upload.thumbnail", actor_id=user.get("id"),
              metadata={"filename": file.filename, "size_kb": round(size / 1024, 1), "path": str(dest_path)})

    return {
        "path": str(dest_path),
        "filename": file.filename,
        "size_bytes": size,
    }
