from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.schemas.user_schema import UserSignup, UserLogin, UserPasswordUpdate, UserProfile, UserProfileUpdate
from app.db.database import get_session
from app.models.productivity_model import Achievement, Notification, UserAchievement
from app.services.auth_service import create_user, authenticate_user, delete_user_by_id, expire_access_token
from app.services.avatar_storage_service import delete_avatar, upload_avatar
from app.utils.auth import get_current_user, oauth2_scheme
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt_handler import create_access_token
from app.utils.timezone import normalize_timezone, utc_now
from PIL import Image, UnidentifiedImageError

router = APIRouter(prefix="/auth", tags=["Auth"])

# Avatar upload constraints
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB
MAX_AVATAR_DIMENSION = 1024  # max width or height in pixels
AVATAR_OUTPUT_SIZE = 256  # final square size (pixels)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _delete_local_avatar_file(avatar: str | None) -> None:
    """Delete a local avatar file if it points inside uploads/avatars."""
    if not avatar:
        return

    try:
        if not isinstance(avatar, str) or not (avatar.startswith("/uploads/") or avatar.startswith("uploads/")):
            return

        target = Path(avatar.lstrip("/"))
        uploads_dir = (Path("uploads") / "avatars").resolve()
        try:
            resolved = target.resolve()
        except Exception:
            resolved = (Path.cwd() / target).resolve()

        if resolved.is_relative_to(uploads_dir) and resolved.exists() and resolved.is_file():
            resolved.unlink()
    except Exception:
        pass


def _profile_response(user) -> UserProfile:
    return UserProfile(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        academic_focus=user.academic_focus,
        bio=user.bio,
        avatar_url=user.avatar_url,
        timezone=normalize_timezone(getattr(user, "timezone", None)),
        last_login=user.last_login,
        created_at=user.created_at,
    )


def _unlock_account_created_achievement(user_id: int, session: Session) -> None:
    achievement = session.exec(
        select(Achievement).where(Achievement.key == "account_created")
    ).first()
    if not achievement:
        achievement = Achievement(
            key="account_created",
            title="Welcome to FocusSpark",
            description="Create your FocusSpark account.",
            badge_icon="user-check",
            criteria_type="account_created",
            criteria_target=1,
            criteria_data={"tier": "bronze"},
        )
        session.add(achievement)
        session.flush()

    if achievement.id is None:
        session.flush()
    if achievement.id is None:
        return

    existing = session.exec(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
        )
    ).first()
    if existing:
        return

    session.add(
        UserAchievement(
            user_id=user_id,
            achievement_id=achievement.id,
            achievement_title=achievement.title,
        )
    )
    session.add(
        Notification(
            user_id=user_id,
            type="achievement",
            title="Achievement unlocked",
            message=f"You unlocked {achievement.title}.",
        )
    )


@router.post("/signup")
def signup(user: UserSignup, session: Session = Depends(get_session)):
    try:
        new_user = create_user(user, session)
        if new_user.id is not None:
            _unlock_account_created_achievement(new_user.id, session)
            session.commit()
        token = create_access_token({"user_id": new_user.id})
        return {
            "message": "User created successfully",
            "user_id": new_user.id,
            "token_type": "bearer",
            "access_token": token,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(user: UserLogin, session: Session = Depends(get_session)):

    db_user = authenticate_user(user, session)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    db_user.last_login = utc_now()
    db_user.updated_at = utc_now()
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    token = create_access_token({"user_id": db_user.id})
    return {"token_type": "bearer", "access_token": token}


@router.patch("/password")
def change_password(
    payload: UserPasswordUpdate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if verify_password(payload.new_password, user.password):
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    user.password = hash_password(payload.new_password)
    user.updated_at = utc_now()
    session.add(user)
    session.commit()

    return {"message": "Password updated successfully"}


@router.get("/profile", response_model=UserProfile)
def profile(user=Depends(get_current_user)):
    if user.id is None:
        raise HTTPException(status_code=500, detail="User record is invalid")

    return _profile_response(user)


@router.patch("/profile", response_model=UserProfile)
def update_profile(
    payload: UserProfileUpdate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    if payload.full_name is not None:
        trimmed_name = payload.full_name.strip()
        if not trimmed_name:
            raise HTTPException(status_code=400, detail="Full name cannot be empty")
        user.full_name = trimmed_name
    if payload.academic_focus is not None:
        user.academic_focus = payload.academic_focus
    if payload.bio is not None:
        user.bio = payload.bio.strip() or None
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url.strip() or None
    if payload.timezone is not None:
        user.timezone = normalize_timezone(payload.timezone)

    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)

    return _profile_response(user)


@router.post("/profile/avatar", response_model=UserProfile)
async def upload_profile_avatar(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    if user.id is None:
        raise HTTPException(status_code=500, detail="User record is invalid")
    # Basic content type check
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Avatar must be an image file")

    # Read bytes and enforce size limit
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Avatar file is empty")
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail=f"Avatar must be <= {MAX_AVATAR_SIZE // (1024*1024)} MB")

    # Validate and normalize image using Pillow
    try:
        img = Image.open(BytesIO(contents))
        img.verify()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to process image file")

    # Re-open (Pillow requires re-opening after verify)
    try:
        img = Image.open(BytesIO(contents)).convert("RGBA")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to open image for processing")

    width, height = img.size
    if width > MAX_AVATAR_DIMENSION or height > MAX_AVATAR_DIMENSION:
        # Resize down while preserving aspect ratio
        img.thumbnail((MAX_AVATAR_DIMENSION, MAX_AVATAR_DIMENSION))

    # Center-crop to square then resize to output size
    width, height = img.size
    min_side = min(width, height)
    left = (width - min_side) // 2
    top = (height - min_side) // 2
    right = left + min_side
    bottom = top + min_side
    img = img.crop((left, top, right, bottom)).resize((AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE))

    # Determine extension/format for saving
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        extension = ".png"

    format_map = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF", ".webp": "WEBP"}
    out_format = format_map.get(extension, "PNG")

    # Save processed image to bytes before uploading to Cloudinary
    out_buffer = BytesIO()
    save_params = {"format": out_format}
    if out_format == "JPEG":
        # Remove alpha for JPEG and set quality
        rgb = Image.new("RGB", img.size, (255, 255, 255))
        rgb.paste(img, mask=img.split()[3])
        rgb.save(out_buffer, quality=90, **save_params)
    else:
        img.save(out_buffer, **save_params)

    avatar_bytes = out_buffer.getvalue()
    if len(avatar_bytes) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="Processed avatar exceeds size limit")

    old_avatar_url = user.avatar_url
    old_avatar_public_id = getattr(user, "avatar_public_id", None)

    uploaded_avatar = upload_avatar(user.id, avatar_bytes, AVATAR_OUTPUT_SIZE)

    # Persist URL to DB
    user.avatar_url = uploaded_avatar.url
    user.avatar_public_id = uploaded_avatar.public_id
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    _delete_local_avatar_file(old_avatar_url)
    if old_avatar_public_id and old_avatar_public_id != uploaded_avatar.public_id:
        delete_avatar(old_avatar_public_id)

    return _profile_response(user)


@router.delete("/profile/avatar", response_model=UserProfile)
def remove_profile_avatar(session: Session = Depends(get_session), user=Depends(get_current_user)):
    """Remove the user's avatar file (if local) and clear the DB field."""
    if user.id is None:
        raise HTTPException(status_code=500, detail="User record is invalid")

    avatar = user.avatar_url
    avatar_public_id = getattr(user, "avatar_public_id", None)
    # If there's no avatar set, return 404
    if not avatar and not avatar_public_id:
        raise HTTPException(status_code=404, detail="No avatar to remove")

    _delete_local_avatar_file(avatar)
    delete_avatar(avatar_public_id)

    # Clear DB field and commit
    user.avatar_url = None
    user.avatar_public_id = None
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)

    return _profile_response(user)

@router.delete("/delete-user")
def delete_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    expire_access_token(token, user.id, session)
    deleted = delete_user_by_id(user.id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}
