from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.chat_model import Document
from app.models.flashcard_model import FlashcardDeck
from app.models.productivity_model import Achievement, Notification, StudySession, UserAchievement
from app.models.quiz_model import Quiz
from app.models.user_model import User
from app.utils.timezone import utc_now, user_local_date, user_local_hour


@dataclass
class AchievementProgressContext:
    sessions: list[StudySession]
    documents_count: int
    quizzes_count: int
    flashcard_decks_count: int


def build_achievement_progress_context(user, db: Session) -> AchievementProgressContext:
    return AchievementProgressContext(
        sessions=db.exec(select(StudySession).where(StudySession.user_id == user.id)).all(),
        documents_count=db.exec(select(func.count(Document.id)).where(Document.user_id == user.id)).one(),
        quizzes_count=db.exec(select(func.count(Quiz.id)).where(Quiz.user_id == user.id)).one(),
        flashcard_decks_count=db.exec(select(func.count(FlashcardDeck.id)).where(FlashcardDeck.user_id == user.id)).one(),
    )


def _achievement_window_start(achievement: Achievement) -> datetime | None:
    if achievement.criteria_window_days is None:
        return None
    return utc_now() - timedelta(days=achievement.criteria_window_days)


def _session_minutes(session: StudySession) -> int:
    return int(session.actual_duration_minutes or session.planned_duration_minutes or 0)


def _session_focus_score(session: StudySession) -> int:
    if not session.completed or session.session_type != "work":
        return 0
    return 100 if (session.distraction_count or 0) == 0 else max(0, 100 - ((session.distraction_count or 0) * 10))


def compute_achievement_progress(
    achievement: Achievement,
    user,
    db: Session,
    context: AchievementProgressContext | None = None,
) -> tuple[int, int]:
    target = max(achievement.criteria_target or 1, 1)
    metric = (achievement.criteria_type or "sessions_completed").lower()
    window_start = _achievement_window_start(achievement)

    if context is None:
        context = build_achievement_progress_context(user, db)

    sessions = [
        session
        for session in context.sessions
        if window_start is None or session.started_at >= window_start
    ]

    if metric in {"sessions_completed", "completed_sessions"}:
        current = sum(1 for session in sessions if session.completed)
    elif metric == "account_created":
        current = 1
    elif metric in {"work_sessions_completed", "work_sessions"}:
        current = sum(1 for session in sessions if session.completed and session.session_type == "work")
    elif metric in {"focus_minutes", "study_minutes"}:
        current = sum(
            _session_minutes(session)
            for session in sessions
            if session.completed and session.session_type == "work"
        )
    elif metric in {"distraction_free_sessions", "zero_distraction_sessions"}:
        current = sum(1 for session in sessions if session.completed and (session.distraction_count or 0) == 0)
    elif metric == "average_focus":
        work_sessions = [session for session in sessions if session.completed and session.session_type == "work"]
        current = (
            round(sum(_session_focus_score(session) for session in work_sessions) / len(work_sessions))
            if work_sessions
            else 0
        )
    elif metric == "early_sessions":
        current = sum(1 for session in sessions if session.started_at and user_local_hour(session.started_at, user) < 7)
    elif metric == "late_sessions":
        current = sum(1 for session in sessions if session.started_at and user_local_hour(session.started_at, user) == 0)
    elif metric == "daily_sessions":
        counts: dict[date, int] = {}
        for session in sessions:
            if not session.completed or not session.started_at:
                continue
            session_date = user_local_date(session.started_at, user)
            counts[session_date] = counts.get(session_date, 0) + 1
        current = max(counts.values(), default=0)
    elif metric == "documents_uploaded":
        current = context.documents_count
    elif metric in {"quizzes_created", "quiz_created"}:
        current = context.quizzes_count
    elif metric in {"flashcard_decks_created", "flashcards_created"}:
        current = context.flashcard_decks_count
    elif metric in {"streak_days", "current_streak"}:
        current = int(getattr(user, "current_streak", 0) or 0)
    elif metric == "total_focus_minutes":
        current = int(getattr(user, "total_focus_minutes", 0) or 0)
    else:
        current = 0

    return current, target


def award_earned_achievements(user, db: Session) -> list[Notification]:
    achievements = db.exec(select(Achievement).order_by(Achievement.id.asc())).all()
    existing = db.exec(select(UserAchievement).where(UserAchievement.user_id == user.id)).all()
    existing_ids = {item.achievement_id for item in existing}
    existing_notification_messages = {
        item.message
        for item in db.exec(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.type == "achievement",
            )
        ).all()
    }
    created_notifications: list[Notification] = []
    changed = False
    progress_context = build_achievement_progress_context(user, db)

    for achievement in achievements:
        if achievement.id is None:
            continue

        achievement_message = f"You unlocked {achievement.title}."
        if achievement.id in existing_ids:
            continue

        current, target = compute_achievement_progress(achievement, user, db, progress_context)
        if current < target:
            continue

        db.add(
            UserAchievement(
                user_id=user.id,
                achievement_id=achievement.id,
                achievement_title=achievement.title,
            )
        )
        notification = Notification(
            user_id=user.id,
            type="achievement",
            title="Achievement unlocked",
            message=achievement_message,
        )
        db.add(notification)
        created_notifications.append(notification)
        existing_ids.add(achievement.id)
        existing_notification_messages.add(achievement_message)
        changed = True

    if changed:
        db.commit()
        for notification in created_notifications:
            db.refresh(notification)

    return created_notifications


def award_earned_achievements_for_user(user_id: int, db: Session) -> list[Notification]:
    user = db.get(User, user_id)
    if user is None:
        return []
    return award_earned_achievements(user, db)
