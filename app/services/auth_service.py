import secrets
from datetime import timedelta
from hashlib import sha256

from sqlmodel import Session, select
from app.models.chat_model import ChatMessage, ChatThread, Document, MessageArtifact
from app.models.flashcard_model import Flashcard, FlashcardDeck, FlashcardReview
from app.models.productivity_model import (
    DistractionEvent,
    EmotionLog,
    Notification,
    StudyGoal,
    StudySession,
    UserAchievement,
    UserSettings,
)
from app.models.quiz_model import Quiz, QuizAttempt, QuizAttemptAnswer, QuizQuestion
from app.models.token_model import ExpiredToken
from app.models.user_model import User
from app.schemas.user_schema import UserSignup, UserLogin
from app.core.config import EMAIL_VERIFICATION_OTP_MINUTES, PASSWORD_RESET_OTP_MINUTES
from app.services.email_service import (
    send_password_changed_email,
    send_password_reset_otp_email,
    send_verification_otp_email,
)
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt_handler import get_token_expiration
from app.utils.timezone import normalize_timezone, utc_now


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _otp_hash(email: str, otp: str) -> str:
    return sha256(f"{email.lower()}:{otp}".encode("utf-8")).hexdigest()


def _password_meets_requirements(password: str) -> bool:
    return len(password) >= 8 and any(char.isalpha() for char in password) and any(char.isdigit() for char in password)


def issue_email_verification_otp(user: User, session: Session) -> str:
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = utc_now()
    user.email_verification_otp_hash = _otp_hash(user.email, otp)
    user.email_verification_expires_at = now + timedelta(minutes=EMAIL_VERIFICATION_OTP_MINUTES)
    user.email_verification_sent_at = now
    user.updated_at = now
    session.add(user)
    session.commit()
    session.refresh(user)
    send_verification_otp_email(user.email, user.full_name, otp, EMAIL_VERIFICATION_OTP_MINUTES)
    return otp


def verify_email_otp(email: str, otp: str, session: Session):
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    if not user:
        raise ValueError("No signup verification found for this email")
    if user.is_email_verified:
        raise ValueError("Email is already verified")
    if not user.email_verification_otp_hash or not user.email_verification_expires_at:
        raise ValueError("Verification code has not been requested")
    if user.email_verification_expires_at < utc_now():
        raise ValueError("Verification code expired. Please request a new code")
    if user.email_verification_otp_hash != _otp_hash(user.email, otp.strip()):
        raise ValueError("Invalid verification code")

    user.is_email_verified = True
    user.email_verification_otp_hash = None
    user.email_verification_expires_at = None
    user.email_verification_sent_at = None
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def issue_password_reset_otp(email: str, session: Session):
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    if not user:
        raise ValueError("No account found with this email")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = utc_now()
    user.password_reset_otp_hash = _otp_hash(user.email, otp)
    user.password_reset_expires_at = now + timedelta(minutes=PASSWORD_RESET_OTP_MINUTES)
    user.password_reset_sent_at = now
    user.updated_at = now
    session.add(user)
    session.commit()
    session.refresh(user)
    send_password_reset_otp_email(user.email, user.full_name, otp, PASSWORD_RESET_OTP_MINUTES)
    return user


def verify_password_reset_otp(email: str, otp: str, session: Session):
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    if not user:
        raise ValueError("No password reset request found for this email")
    if not user.password_reset_otp_hash or not user.password_reset_expires_at:
        raise ValueError("Password reset code has not been requested")
    if user.password_reset_expires_at < utc_now():
        raise ValueError("Password reset code expired. Please request a new code")
    if user.password_reset_otp_hash != _otp_hash(user.email, otp.strip()):
        raise ValueError("Invalid password reset code")

    return user


def reset_password_with_otp(email: str, otp: str, new_password: str, confirm_password: str, session: Session):
    if new_password != confirm_password:
        raise ValueError("New passwords do not match")
    if not _password_meets_requirements(new_password):
        raise ValueError("Password must be at least 8 characters, including a letter and a number")

    user = verify_password_reset_otp(email, otp, session)
    if verify_password(new_password, user.password):
        raise ValueError("New password must be different from current password")

    user.password = hash_password(new_password)
    user.password_reset_otp_hash = None
    user.password_reset_expires_at = None
    user.password_reset_sent_at = None
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    send_password_changed_email(user.email, user.full_name)
    return user


def create_user(user_data: UserSignup, session: Session):
    # check password match
    if user_data.password != user_data.confirm_password:
        raise ValueError("Passwords do not match")

    if not _password_meets_requirements(user_data.password):
        raise ValueError("Password must be at least 8 characters, including a letter and a number")
    
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
        is_email_verified=False,
        timezone=normalize_timezone(user_data.timezone),
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


def expire_access_token(token: str, user_id: int | None, session: Session):
    token_hash = _token_hash(token)
    existing = session.exec(select(ExpiredToken).where(ExpiredToken.token_hash == token_hash)).first()
    if existing:
        return existing

    expired_token = ExpiredToken(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=get_token_expiration(token),
    )
    session.add(expired_token)
    session.flush()
    return expired_token


def is_access_token_expired(token: str, session: Session) -> bool:
    token_hash = _token_hash(token)
    expired_token = session.exec(select(ExpiredToken).where(ExpiredToken.token_hash == token_hash)).first()
    if not expired_token:
        return False

    if expired_token.expires_at and expired_token.expires_at < utc_now():
        session.delete(expired_token)
        session.commit()
        return False

    return True


def delete_user_by_id(user_id: int, session: Session):
    user = get_user_by_id(user_id, session)
    if not user:
        return False

    quiz_attempts = session.exec(select(QuizAttempt).where(QuizAttempt.user_id == user_id)).all()
    attempt_ids = [attempt.id for attempt in quiz_attempts if attempt.id is not None]
    quiz_attempt_answers = (
        session.exec(select(QuizAttemptAnswer).where(QuizAttemptAnswer.attempt_id.in_(attempt_ids))).all()
        if attempt_ids
        else []
    )
    quizzes = session.exec(select(Quiz).where(Quiz.user_id == user_id)).all()
    quiz_ids = [quiz.id for quiz in quizzes if quiz.id is not None]
    quiz_questions = (
        session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids))).all()
        if quiz_ids
        else []
    )

    flashcard_decks = session.exec(select(FlashcardDeck).where(FlashcardDeck.user_id == user_id)).all()
    deck_ids = [deck.id for deck in flashcard_decks if deck.id is not None]
    flashcards = (
        session.exec(select(Flashcard).where(Flashcard.deck_id.in_(deck_ids))).all()
        if deck_ids
        else []
    )
    flashcard_reviews = session.exec(select(FlashcardReview).where(FlashcardReview.user_id == user_id)).all()

    chat_threads = session.exec(select(ChatThread).where(ChatThread.user_id == user_id)).all()
    thread_ids = [thread.id for thread in chat_threads if thread.id is not None]
    chat_messages = (
        session.exec(select(ChatMessage).where(ChatMessage.thread_id.in_(thread_ids))).all()
        if thread_ids
        else []
    )
    message_ids = [message.id for message in chat_messages if message.id is not None]
    message_artifacts = (
        session.exec(select(MessageArtifact).where(MessageArtifact.message_id.in_(message_ids))).all()
        if message_ids
        else []
    )

    delete_groups = [
        quiz_attempt_answers,
        quiz_attempts,
        quiz_questions,
        quizzes,
        flashcard_reviews,
        flashcards,
        flashcard_decks,
        message_artifacts,
        chat_messages,
        chat_threads,
        session.exec(select(Document).where(Document.user_id == user_id)).all(),
        session.exec(select(DistractionEvent).where(DistractionEvent.user_id == user_id)).all(),
        session.exec(select(EmotionLog).where(EmotionLog.user_id == user_id)).all(),
        session.exec(select(StudySession).where(StudySession.user_id == user_id)).all(),
        session.exec(select(StudyGoal).where(StudyGoal.user_id == user_id)).all(),
        session.exec(select(UserAchievement).where(UserAchievement.user_id == user_id)).all(),
        session.exec(select(Notification).where(Notification.user_id == user_id)).all(),
        session.exec(select(UserSettings).where(UserSettings.user_id == user_id)).all(),
    ]

    for records in delete_groups:
        for record in records:
            session.delete(record)
        session.flush()

    session.delete(user)
    session.commit()
    return True
