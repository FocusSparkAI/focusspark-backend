from sqlmodel import Session, select
from app.models.user_model import User
from app.schemas.user_schema import UserSignup, UserLogin
from app.utils.hashing import hash_password, verify_password


def create_user(user_data: UserSignup, session: Session):
    # check password match
    if user_data.password != user_data.confirm_password:
        raise ValueError("Passwords do not match")
    
    # check terms acceptance
    if not user_data.accepted_terms:
        raise ValueError("You must accept the terms and conditions")

    # check if email exists
    statement = select(User).where(User.email == user_data.email)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise ValueError("Email already registered")

    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        password=hash_password(user_data.password),
        academic_focus=user_data.academic_focus,
        accepted_terms=user_data.accepted_terms,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(user: UserLogin, session: Session):
    statement = select(User).where(User.email == user.email)
    db_user = session.exec(statement).first()
    if not db_user:
        return None

    if not verify_password(user.password, db_user.password):
        return None

    return db_user


def get_user_by_id(user_id: int, session: Session):
    statement = select(User).where(User.id == user_id)
    return session.exec(statement).first()


def delete_user_by_id(user_id: int, session: Session):
    user = get_user_by_id(user_id, session)
    if not user:
        return False

    session.delete(user)
    session.commit()
    return True