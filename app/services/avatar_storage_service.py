from dataclasses import dataclass
from io import BytesIO

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException

from app.core.config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME


@dataclass(frozen=True)
class AvatarUploadResult:
    url: str
    public_id: str


def _configure_cloudinary() -> None:
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise HTTPException(status_code=500, detail="Cloudinary is not configured")

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_avatar(user_id: int, avatar_bytes: bytes, size: int) -> AvatarUploadResult:
    _configure_cloudinary()
    try:
        upload_result = cloudinary.uploader.upload(
            BytesIO(avatar_bytes),
            folder="focusspark/avatars",
            public_id=f"user-{user_id}",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": size, "height": size, "crop": "fill", "gravity": "auto"},
                {"quality": "auto", "fetch_format": "auto"},
            ],
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Could not upload avatar")

    secure_url = upload_result.get("secure_url")
    public_id = upload_result.get("public_id")
    if not secure_url or not public_id:
        raise HTTPException(status_code=502, detail="Cloudinary upload did not return avatar details")

    return AvatarUploadResult(url=secure_url, public_id=public_id)


def delete_avatar(public_id: str | None) -> None:
    if not public_id:
        return

    try:
        _configure_cloudinary()
        cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception:
        pass
