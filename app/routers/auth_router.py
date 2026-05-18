from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.schemas.user_schema import UserSignup, UserLogin, UserProfile
from app.db.database import get_session
from app.services.auth_service import create_user, authenticate_user, delete_user_by_id
from app.utils.auth import get_current_user
from app.utils.jwt_handler import create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


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


@router.get("/profile", response_model=UserProfile)
def profile(user=Depends(get_current_user)):
    if user.id is None:
        raise HTTPException(status_code=500, detail="User record is invalid")

    return UserProfile(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        academic_focus=user.academic_focus,
        created_at=user.created_at,
    )


@router.delete("/delete-user")
def delete_user(session: Session = Depends(get_session), user=Depends(get_current_user)):
    deleted = delete_user_by_id(user.id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}