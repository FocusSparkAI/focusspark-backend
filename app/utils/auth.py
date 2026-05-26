from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.db.database import get_session
from app.services.auth_service import get_user_by_id, is_access_token_expired
from app.utils.jwt_handler import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def resolve_user_from_token(token: str, session: Session):
    if is_access_token_expired(token, session):
        raise HTTPException(status_code=401, detail="Token expired")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
):
    return resolve_user_from_token(token, session)
