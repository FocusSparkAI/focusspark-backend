from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session
from datetime import datetime

from app.schemas.user_schema import UserSignup, UserLogin, UserPasswordUpdate, UserProfile, UserProfileUpdate
from app.db.database import get_session
from app.services.auth_service import create_user, authenticate_user, delete_user_by_id
from app.utils.auth import get_current_user
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt_handler import create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


def _profile_response(user) -> UserProfile:
    return UserProfile(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        academic_focus=user.academic_focus,
        bio=user.bio,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


@router.post("/signup")
def signup(user: UserSignup, session: Session = Depends(get_session)):
    try:
        new_user = create_user(user, session)
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
    user.updated_at = datetime.utcnow()
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

    user.updated_at = datetime.utcnow()
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

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Avatar must be an image file")

    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        extension = ".png"

    uploads_dir = Path("uploads") / "avatars"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    avatar_filename = f"user-{user.id}-{uuid4().hex}{extension}"
    avatar_path = uploads_dir / avatar_filename

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Avatar file is empty")
    avatar_path.write_bytes(contents)

    user.avatar_url = f"/uploads/avatars/{avatar_filename}"
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)

    return _profile_response(user)


@router.delete("/delete-user")
def delete_user(session: Session = Depends(get_session), user=Depends(get_current_user)):
    deleted = delete_user_by_id(user.id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}
