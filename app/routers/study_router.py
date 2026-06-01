import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.db.database import get_session
from app.models.chat_model import ChatMessage, ChatThread, Document, MessageArtifact
from app.models.flashcard_model import Flashcard, FlashcardDeck, FlashcardReview
from app.models.productivity_model import (
    Achievement,
    DistractionEvent,
    EmotionLog,
    Notification,
    StudyGoal,
    StudySession,
    UserAchievement,
    UserSettings,
)
from app.models.quiz_model import Quiz, QuizAttempt, QuizAttemptAnswer, QuizQuestion
from app.services.achievement_service import award_earned_achievements, compute_achievement_progress
from app.utils.auth import get_current_user
from app.utils.timezone import (
    utc_now,
    user_day_start_utc,
    user_local_date,
    user_local_hour,
    user_today,
)


router = APIRouter(prefix="/study", tags=["Study"])


class StudySessionCreate(BaseModel):
    session_type: str = PydanticField(default="work")
    planned_duration_minutes: int = PydanticField(gt=0)
    started_at: Optional[datetime] = None
    notes: Optional[str] = None


class StudySessionComplete(BaseModel):
    ended_at: Optional[datetime] = None
    actual_duration_minutes: Optional[int] = PydanticField(default=None, ge=0)
    distraction_count: Optional[int] = PydanticField(default=None, ge=0)
    notes: Optional[str] = None


class DistractionCreate(BaseModel):
    event_type: str = "tab_switch"
    source: str = "frontend"
    confidence_score: Optional[float] = None
    productive: Optional[bool] = None
    payload: Optional[dict] = None
    detected_at: Optional[datetime] = None


class EmotionCreate(BaseModel):
    emotion: str
    confidence_score: Optional[float] = None
    detected_at: Optional[datetime] = None


class StudyGoalCreate(BaseModel):
    title: str = "Study"
    target_minutes: int = PydanticField(ge=5)
    current_minutes: int = PydanticField(default=0, ge=0)
    goal_date: Optional[date] = None
    position: Optional[int] = None
    due_date: Optional[date] = None


class StudyGoalUpdate(BaseModel):
    title: Optional[str] = None
    target_minutes: Optional[int] = PydanticField(default=None, ge=5)
    current_minutes: Optional[int] = PydanticField(default=None, ge=0)
    completed: Optional[bool] = None
    goal_date: Optional[date] = None
    position: Optional[int] = None
    due_date: Optional[date] = None


class NotificationUpdate(BaseModel):
    read: bool = True


class UserSettingsUpdate(BaseModel):
    dark_mode: Optional[bool] = None
    pomodoro_duration_minutes: Optional[int] = PydanticField(default=None, gt=0)
    break_duration_minutes: Optional[int] = PydanticField(default=None, ge=0)
    ai_persona: Optional[str] = None
    preferred_ai_provider: Optional[Literal["openai", "gemini"]] = None
    preferred_ai_model: Optional[str] = None
    focus_sensitivity: Optional[str] = None
    fallback_method: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    focus_alerts_enabled: Optional[bool] = None
    integrations: Optional[dict] = None
    appearance: Optional[dict] = None
    accessibility: Optional[dict] = None
    privacy: Optional[dict] = None


class AchievementResponse(BaseModel):
    id: int
    key: Optional[str] = None
    title: str
    description: Optional[str] = None
    badge_icon: Optional[str] = None
    criteria_type: Optional[str] = None
    criteria_target: int
    criteria_window_days: Optional[int] = None
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    achievement_title: Optional[str] = None
    progress_current: int
    progress_target: int
    tier: str = "bronze"
    unlock_order: int = 999


ACHIEVEMENT_UNLOCK_ORDER = [
    "account_created",
    "first_session",
    "first_quiz",
    "first_flashcard_deck",
    "first_document",
    "early_bird",
    "night_owl",
    "focus_master",
    "quiz_builder",
    "flashcard_builder",
    "streak_starter",
    "momentum_builder",
    "marathon_runner",
    "focus_champion",
    "knowledge_seeker",
    "session_collector",
    "perfect_score",
    "consistency_king",
]


def _achievement_unlock_order(achievement: Achievement) -> int:
    try:
        return ACHIEVEMENT_UNLOCK_ORDER.index(achievement.key or "")
    except ValueError:
        return len(ACHIEVEMENT_UNLOCK_ORDER)


def _ordered_achievements(db: Session) -> list[Achievement]:
    achievements = db.exec(select(Achievement).order_by(Achievement.id.asc())).all()
    return sorted(
        achievements,
        key=lambda achievement: (
            _achievement_unlock_order(achievement),
            achievement.criteria_target or 0,
            achievement.title,
        ),
    )


def _get_owned_session(session_id: int, user_id: int, db: Session) -> StudySession:
    study_session = db.get(StudySession, session_id)
    if not study_session or study_session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Study session not found")
    return study_session


def _get_owned_goal(goal_id: int, user_id: int, db: Session) -> StudyGoal:
    study_goal = db.get(StudyGoal, goal_id)
    if not study_goal or study_goal.user_id != user_id:
        raise HTTPException(status_code=404, detail="Study goal not found")
    return study_goal


def _goal_day(goal: StudyGoal, user=None) -> date:
    if getattr(goal, "goal_date", None):
        return goal.goal_date
    if goal.due_date:
        return goal.due_date
    if goal.created_at and user is not None:
        return user_local_date(goal.created_at, user)
    return goal.created_at.date() if goal.created_at else utc_now().date()


def _goal_sort_key(goal: StudyGoal):
    return (goal.completed, _goal_day(goal), goal.position or 0, goal.id or 0)


def _next_goal_position(user_id: int, goal_day: date, db: Session) -> int:
    goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user_id)).all()
    same_day_positions = [
        int(goal.position or 0)
        for goal in goals
        if _goal_day(goal) == goal_day
    ]
    return (max(same_day_positions) + 1) if same_day_positions else 1


def _sync_goal_completion(goal: StudyGoal, now: Optional[datetime] = None) -> None:
    timestamp = now or utc_now()
    goal.completed = goal.current_minutes >= goal.target_minutes
    goal.completed_at = timestamp if goal.completed else None
    goal.updated_at = timestamp


def _allocate_session_minutes_to_goals(
    user_id: int,
    session_day: date,
    minutes: int,
    db: Session,
) -> None:
    remaining = max(0, minutes)
    if remaining <= 0:
        return

    goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user_id)).all()
    todays_goals = sorted(
        [goal for goal in goals if _goal_day(goal) == session_day and not goal.completed],
        key=lambda goal: (goal.position or 0, goal.id or 0),
    )

    now = utc_now()
    for goal in todays_goals:
        if remaining <= 0:
            break

        needed = max(0, goal.target_minutes - goal.current_minutes)
        if needed <= 0:
            _sync_goal_completion(goal, now)
            db.add(goal)
            continue

        applied = min(needed, remaining)
        goal.current_minutes += applied
        remaining -= applied
        _sync_goal_completion(goal, now)
        db.add(goal)


def _goals_for_day(user_id: int, goal_day: date, db: Session) -> list[StudyGoal]:
    goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user_id)).all()
    return sorted(
        [goal for goal in goals if _goal_day(goal) == goal_day],
        key=lambda goal: (goal.completed, goal.position or 0, goal.id or 0),
    )


def _goal_stats(goals: list[StudyGoal]) -> dict:
    completed = [goal for goal in goals if goal.completed]
    incomplete = [goal for goal in goals if not goal.completed]
    total_target = sum(goal.target_minutes for goal in goals)
    total_progress = sum(min(goal.current_minutes, goal.target_minutes) for goal in goals)
    return {
        "total": len(goals),
        "completed": len(completed),
        "incomplete": len(incomplete),
        "target_minutes": total_target,
        "progress_minutes": total_progress,
        "completion_rate": round((len(completed) / len(goals)) * 100) if goals else 0,
    }


def _goals_between(user_id: int, start_day: date, end_day: date, db: Session) -> list[StudyGoal]:
    goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user_id)).all()
    return [goal for goal in goals if start_day <= _goal_day(goal) <= end_day]


def _get_user_settings(user_id: int, db: Session) -> UserSettings:
    settings = db.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()
    if settings:
        return settings

    settings = UserSettings(user_id=user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _history_bounds(
    start_date: Optional[date],
    end_date: Optional[date],
) -> tuple[Optional[datetime], Optional[datetime]]:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    start_dt = datetime.combine(start_date, time.min) if start_date else None
    end_dt = datetime.combine(end_date, time.max) if end_date else None
    return start_dt, end_dt


def _user_sessions_query(
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    start_dt, end_dt = _history_bounds(start_date, end_date)

    statement = select(StudySession).where(StudySession.user_id == user_id)
    if start_dt is not None:
        statement = statement.where(StudySession.started_at >= start_dt)
    if end_dt is not None:
        statement = statement.where(StudySession.started_at <= end_dt)

    return statement.order_by(StudySession.started_at.desc(), StudySession.id.desc())


def _achievement_window_start(achievement: Achievement) -> Optional[datetime]:
    if achievement.criteria_window_days is None:
        return None
    return utc_now() - timedelta(days=achievement.criteria_window_days)


def _compute_achievement_progress(
    achievement: Achievement,
    user,
    db: Session,
) -> tuple[int, int]:
    return compute_achievement_progress(achievement, user, db)


def _session_minutes(session: StudySession) -> int:
    return int(session.actual_duration_minutes or session.planned_duration_minutes or 0)


def _session_focus_score(session: StudySession) -> int:
    if not session.completed or session.session_type != "work":
        return 0
    return 100 if (session.distraction_count or 0) == 0 else max(0, 100 - ((session.distraction_count or 0) * 10))


def _current_streak_from_dates(study_dates: set[date], today: date) -> int:
    if not study_dates:
        return 0

    anchor = today if today in study_dates else today - timedelta(days=1)
    streak = 0
    cursor = anchor
    while cursor in study_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _longest_streak_from_dates(study_dates: set[date]) -> int:
    if not study_dates:
        return 0

    longest = 0
    current = 0
    previous_day: Optional[date] = None
    for study_day in sorted(study_dates):
        if previous_day is not None and study_day == previous_day + timedelta(days=1):
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous_day = study_day
    return longest


def _recalculate_user_progress(user, db: Session) -> None:
    sessions = db.exec(
        select(StudySession).where(
            StudySession.user_id == user.id,
            StudySession.completed == True,  # noqa: E712
            StudySession.session_type == "work",
        )
    ).all()

    study_dates = {
            user_local_date(session.started_at, user)
        for session in sessions
        if session.started_at is not None and _session_minutes(session) > 0
    }

    user.current_streak = _current_streak_from_dates(study_dates, user_today(user))
    user.longest_streak = _longest_streak_from_dates(study_dates)
    user.total_focus_minutes = sum(_session_minutes(session) for session in sessions)
    user.updated_at = utc_now()
    db.add(user)


def _sessions_for_recent_days(user, db: Session, days: int) -> list[StudySession]:
    start_date = user_day_start_utc(user_today(user) - timedelta(days=days - 1), user)
    return db.exec(
        select(StudySession)
        .where(StudySession.user_id == user.id, StudySession.started_at >= start_date)
        .order_by(StudySession.started_at.asc(), StudySession.id.asc())
    ).all()


def _sessions_for_recent_weeks(user, db: Session, weeks: int) -> list[StudySession]:
    start_date = user_day_start_utc(user_today(user) - timedelta(days=(weeks * 7) - 1), user)
    return db.exec(
        select(StudySession)
        .where(StudySession.user_id == user.id, StudySession.started_at >= start_date)
        .order_by(StudySession.started_at.asc(), StudySession.id.asc())
    ).all()


def _daily_focus_rows(sessions: list[StudySession], user, days: int = 7) -> list[dict]:
    today = user_today(user)
    buckets = {
        today - timedelta(days=offset): {
            "date": today - timedelta(days=offset),
            "minutes": 0,
            "sessions": 0,
            "distractions": 0,
            "focus_scores": [],
        }
        for offset in range(days - 1, -1, -1)
    }

    for session in sessions:
        if not session.started_at:
            continue
        session_day = user_local_date(session.started_at, user)
        if session_day not in buckets:
            continue
        buckets[session_day]["minutes"] += _session_minutes(session) if session.completed else 0
        buckets[session_day]["sessions"] += 1 if session.completed else 0
        buckets[session_day]["distractions"] += session.distraction_count or 0
        if session.completed and session.session_type == "work":
            buckets[session_day]["focus_scores"].append(_session_focus_score(session))

    rows = []
    for item in buckets.values():
        scores = item.pop("focus_scores")
        rows.append(
            {
                "date": item["date"].isoformat(),
                "day": item["date"].strftime("%a"),
                "minutes": item["minutes"],
                "sessions": item["sessions"],
                "distractions": item["distractions"],
                "focus_score": round(sum(scores) / len(scores)) if scores else 0,
            }
        )
    return rows


def _weekly_consistency_rows(sessions: list[StudySession], user, weeks: int = 4) -> list[dict]:
    today = user_today(user)
    rows = []
    for index in range(weeks, 0, -1):
        week_end = today - timedelta(days=(index - 1) * 7)
        week_start = week_end - timedelta(days=6)
        week_sessions = [
            session
            for session in sessions
            if session.started_at and week_start <= user_local_date(session.started_at, user) <= week_end
        ]
        completed = [session for session in week_sessions if session.completed]
        study_days = {user_local_date(session.started_at, user) for session in completed if session.started_at}
        rows.append(
            {
                "week": f"Week {weeks - index + 1}",
                "start_date": week_start.isoformat(),
                "end_date": week_end.isoformat(),
                "study_days": len(study_days),
                "completed_sessions": len(completed),
                "focus_minutes": sum(_session_minutes(session) for session in completed if session.session_type == "work"),
            }
        )
    return rows


def _best_study_window(sessions: list[StudySession], user) -> Optional[dict]:
    hourly_scores: dict[int, list[int]] = defaultdict(list)
    for session in sessions:
        if not session.started_at or not session.completed or session.session_type != "work":
            continue
        hourly_scores[user_local_hour(session.started_at, user)].append(_session_focus_score(session))

    if not hourly_scores:
        return None

    best_hour, scores = max(
        hourly_scores.items(),
        key=lambda item: (sum(item[1]) / len(item[1]), len(item[1])),
    )
    end_hour = (best_hour + 2) % 24
    return {
        "label": f"{best_hour:02d}:00-{end_hour:02d}:00",
        "hour": best_hour,
        "average_focus": round(sum(scores) / len(scores)),
        "sessions": len(scores),
    }


def _serialize_achievement(
    achievement: Achievement,
    user,
    db: Session,
    user_achievement: Optional[UserAchievement] = None,
) -> dict:
    current, target = _compute_achievement_progress(achievement, user, db)
    unlocked = user_achievement is not None

    criteria_data = achievement.criteria_data or {}
    return {
        "id": achievement.id,
        "key": achievement.key,
        "title": achievement.title,
        "description": achievement.description,
        "badge_icon": achievement.badge_icon,
        "criteria_type": achievement.criteria_type,
        "criteria_target": target,
        "criteria_window_days": achievement.criteria_window_days,
        "unlocked": unlocked,
        "unlocked_at": user_achievement.unlocked_at if user_achievement else None,
        "achievement_title": user_achievement.achievement_title if user_achievement else None,
        "progress_current": current,
        "progress_target": target,
        "tier": criteria_data.get("tier") or "bronze",
        "unlock_order": _achievement_unlock_order(achievement),
    }


def _ensure_earned_achievements(user, db: Session) -> None:
    award_earned_achievements(user, db)


def _session_to_dict(session: StudySession) -> dict:
    return session.model_dump(mode="json")


def _settings_to_dict(settings: UserSettings) -> dict:
    return settings.model_dump(mode="json")


def _records_to_dict(records: list) -> list[dict]:
    return [record.model_dump(mode="json") for record in records]


def _export_user_profile(user) -> dict:
    profile = user.model_dump(mode="json")
    profile.pop("password", None)
    profile.pop("avatar_public_id", None)
    return profile


def _delete_records(db: Session, records: list) -> int:
    for record in records:
        db.delete(record)
    db.flush()
    return len(records)


@router.delete("/data")
def clear_account_data(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    deleted_counts = {}

    quiz_attempts = db.exec(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id)
    ).all()
    attempt_ids = [attempt.id for attempt in quiz_attempts if attempt.id is not None]
    quiz_attempt_answers = (
        db.exec(
            select(QuizAttemptAnswer).where(QuizAttemptAnswer.attempt_id.in_(attempt_ids))
        ).all()
        if attempt_ids
        else []
    )
    quizzes = db.exec(select(Quiz).where(Quiz.user_id == user.id)).all()
    quiz_ids = [quiz.id for quiz in quizzes if quiz.id is not None]
    quiz_questions = (
        db.exec(select(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids))).all()
        if quiz_ids
        else []
    )

    flashcard_reviews = db.exec(
        select(FlashcardReview).where(FlashcardReview.user_id == user.id)
    ).all()
    flashcard_decks = db.exec(
        select(FlashcardDeck).where(FlashcardDeck.user_id == user.id)
    ).all()
    deck_ids = [deck.id for deck in flashcard_decks if deck.id is not None]
    flashcards = (
        db.exec(select(Flashcard).where(Flashcard.deck_id.in_(deck_ids))).all()
        if deck_ids
        else []
    )

    chat_threads = db.exec(
        select(ChatThread).where(ChatThread.user_id == user.id)
    ).all()
    thread_ids = [thread.id for thread in chat_threads if thread.id is not None]
    chat_messages = (
        db.exec(select(ChatMessage).where(ChatMessage.thread_id.in_(thread_ids))).all()
        if thread_ids
        else []
    )
    message_ids = [message.id for message in chat_messages if message.id is not None]
    message_artifacts = (
        db.exec(
            select(MessageArtifact).where(MessageArtifact.message_id.in_(message_ids))
        ).all()
        if message_ids
        else []
    )

    delete_groups = [
        ("quiz_attempt_answers", quiz_attempt_answers),
        ("quiz_attempts", quiz_attempts),
        ("quiz_questions", quiz_questions),
        ("quizzes", quizzes),
        ("flashcard_reviews", flashcard_reviews),
        ("flashcards", flashcards),
        ("flashcard_decks", flashcard_decks),
        ("message_artifacts", message_artifacts),
        ("chat_messages", chat_messages),
        ("chat_threads", chat_threads),
        ("documents", db.exec(select(Document).where(Document.user_id == user.id)).all()),
        ("distraction_events", db.exec(select(DistractionEvent).where(DistractionEvent.user_id == user.id)).all()),
        ("emotion_logs", db.exec(select(EmotionLog).where(EmotionLog.user_id == user.id)).all()),
        ("study_sessions", db.exec(select(StudySession).where(StudySession.user_id == user.id)).all()),
        ("study_goals", db.exec(select(StudyGoal).where(StudyGoal.user_id == user.id)).all()),
        ("user_achievements", db.exec(select(UserAchievement).where(UserAchievement.user_id == user.id)).all()),
        ("notifications", db.exec(select(Notification).where(Notification.user_id == user.id)).all()),
    ]

    for name, records in delete_groups:
        deleted_counts[name] = _delete_records(db, records)

    user.current_streak = 0
    user.longest_streak = 0
    user.total_focus_minutes = 0
    user.updated_at = utc_now()
    db.add(user)
    db.commit()

    return {"message": "Account data cleared successfully", "deleted": deleted_counts}


@router.post("/sessions")
def create_study_session(
    payload: StudySessionCreate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_session = StudySession(
        user_id=user.id,
        session_type=payload.session_type,
        started_at=payload.started_at or utc_now(),
        planned_duration_minutes=payload.planned_duration_minutes,
        notes=payload.notes,
    )
    db.add(study_session)
    db.commit()
    db.refresh(study_session)
    session_id = study_session.id
    if session_id is None:
        raise HTTPException(status_code=500, detail="Study session was not saved")
    return study_session.model_dump(mode="json")


@router.patch("/sessions/{session_id}/complete")
def complete_study_session(
    session_id: int,
    payload: StudySessionComplete,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_session = _get_owned_session(session_id, user.id, db)
    was_completed = study_session.completed
    study_session.ended_at = payload.ended_at or utc_now()
    study_session.actual_duration_minutes = payload.actual_duration_minutes
    if payload.distraction_count is not None:
        study_session.distraction_count = payload.distraction_count
    study_session.completed = True
    if payload.notes is not None:
        study_session.notes = payload.notes
    if not was_completed and study_session.session_type == "work":
        _allocate_session_minutes_to_goals(
            user.id,
            user_local_date(study_session.started_at, user) if study_session.started_at else user_today(user),
            _session_minutes(study_session),
            db,
        )
    _recalculate_user_progress(user, db)
    db.add(study_session)
    db.commit()
    db.refresh(study_session)
    award_earned_achievements(user, db)
    return study_session.model_dump(mode="json")


@router.post("/sessions/{session_id}/distractions")
def log_distraction(
    session_id: int,
    payload: DistractionCreate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_session = _get_owned_session(session_id, user.id, db)
    session_pk = study_session.id
    if session_pk is None:
        raise HTTPException(status_code=500, detail="Study session is invalid")
    event = DistractionEvent(
        user_id=user.id,
        session_id=session_pk,
        event_type=payload.event_type,
        source=payload.source,
        confidence_score=payload.confidence_score,
        productive=payload.productive,
        payload=payload.payload,
        detected_at=payload.detected_at or utc_now(),
    )
    study_session.distraction_count += 1
    db.add(event)
    db.add(study_session)
    db.commit()
    db.refresh(event)
    return event.model_dump(mode="json")


@router.post("/sessions/{session_id}/emotions")
def log_emotion(
    session_id: int,
    payload: EmotionCreate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_session = _get_owned_session(session_id, user.id, db)
    session_pk = study_session.id
    if session_pk is None:
        raise HTTPException(status_code=500, detail="Study session is invalid")
    event = EmotionLog(
        user_id=user.id,
        session_id=session_pk,
        emotion=payload.emotion,
        confidence_score=payload.confidence_score,
        detected_at=payload.detected_at or utc_now(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event.model_dump(mode="json")


@router.get("/sessions/recent")
def recent_sessions(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    statement = (
        select(StudySession)
        .where(StudySession.user_id == user.id)
        .order_by(StudySession.started_at.desc(), StudySession.id.desc())
        .limit(limit)
    )
    sessions = db.exec(statement).all()
    return [session.model_dump(mode="json") for session in sessions]


@router.get("/sessions/history")
def session_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    sessions = db.exec(_user_sessions_query(user.id, start_date, end_date)).all()
    return [session.model_dump(mode="json") for session in sessions]


@router.get("/stats/summary")
def productivity_summary(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    sessions = db.exec(
        select(StudySession).where(StudySession.user_id == user.id)
    ).all()

    completed_sessions = [session for session in sessions if session.completed]
    recent_work_sessions = [session for session in completed_sessions if session.session_type == "work"]
    goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user.id)).all()
    goal_stats = _goal_stats(goals)

    total_work_minutes = sum(session.actual_duration_minutes or session.planned_duration_minutes for session in recent_work_sessions)
    total_distractions = sum(session.distraction_count for session in completed_sessions)
    average_focus = (
        round(
            sum(
                100 if session.actual_duration_minutes and session.distraction_count == 0 else max(0, 100 - (session.distraction_count * 10))
                for session in recent_work_sessions
            )
            / len(recent_work_sessions)
        )
        if recent_work_sessions
        else 0
    )

    return {
        "total_sessions": len(sessions),
        "completed_sessions": len(completed_sessions),
        "work_sessions": len(recent_work_sessions),
        "total_work_minutes": total_work_minutes,
        "total_distractions": total_distractions,
        "average_focus": average_focus,
        "current_streak": int(getattr(user, "current_streak", 0) or 0),
        "longest_streak": int(getattr(user, "longest_streak", 0) or 0),
        "goals_total": goal_stats["total"],
        "goals_completed": goal_stats["completed"],
        "goals_incomplete": goal_stats["incomplete"],
        "goal_completion_rate": goal_stats["completion_rate"],
    }


@router.get("/stats/analytics")
def analytics_insights(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    sessions = _sessions_for_recent_weeks(user, db, 4)
    completed = [session for session in sessions if session.completed]
    work_sessions = [session for session in completed if session.session_type == "work"]
    daily_focus = _daily_focus_rows(_sessions_for_recent_days(user, db, 7), user, 7)
    weekly_consistency = _weekly_consistency_rows(sessions, user, 4)
    today = user_today(user)
    recent_goals = _goals_between(user.id, today - timedelta(days=27), today, db)
    recent_goal_stats = _goal_stats(recent_goals)

    best_day = max(daily_focus, key=lambda item: (item["minutes"], item["focus_score"]), default=None)
    best_window = _best_study_window(work_sessions, user)
    total_minutes = sum(_session_minutes(session) for session in work_sessions)
    total_distractions = sum(session.distraction_count or 0 for session in completed)
    average_focus = (
        round(sum(_session_focus_score(session) for session in work_sessions) / len(work_sessions))
        if work_sessions
        else 0
    )

    return {
        "total_focus_minutes": total_minutes,
        "completed_sessions": len(completed),
        "total_distractions": total_distractions,
        "average_focus": average_focus,
        "current_streak": int(getattr(user, "current_streak", 0) or 0),
        "longest_streak": int(getattr(user, "longest_streak", 0) or 0),
        "goals_total": recent_goal_stats["total"],
        "goals_completed": recent_goal_stats["completed"],
        "goals_incomplete": recent_goal_stats["incomplete"],
        "goal_target_minutes": recent_goal_stats["target_minutes"],
        "goal_progress_minutes": recent_goal_stats["progress_minutes"],
        "goal_completion_rate": recent_goal_stats["completion_rate"],
        "daily_focus": daily_focus,
        "weekly_consistency": weekly_consistency,
        "best_focus_day": best_day,
        "best_study_window": best_window,
        "insights": [
            {
                "title": "Best focus day",
                "value": best_day["day"] if best_day and best_day["minutes"] else None,
                "detail": (
                    f"{best_day['minutes']} focused minutes with {best_day['distractions']} distractions"
                    if best_day and best_day["minutes"]
                    else "Complete more sessions to discover your best day"
                ),
            },
            {
                "title": "Best study window",
                "value": best_window["label"] if best_window else None,
                "detail": (
                    f"{best_window['average_focus']}% average focus across {best_window['sessions']} sessions"
                    if best_window
                    else "Complete more sessions to discover your best time"
                ),
            },
            {
                "title": "Consistency",
                "value": f"{getattr(user, 'current_streak', 0) or 0} days",
                "detail": "Current study streak",
            },
            {
                "title": "Goal completion",
                "value": f"{recent_goal_stats['completion_rate']}%" if recent_goal_stats["total"] else None,
                "detail": (
                    f"{recent_goal_stats['completed']} completed, {recent_goal_stats['incomplete']} incomplete"
                    if recent_goal_stats["total"]
                    else "Create daily goals to track completion rate"
                ),
            },
        ],
    }


@router.get("/stats/dashboard")
def dashboard_stats(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    sessions = _sessions_for_recent_days(user, db, 7)
    completed = [session for session in sessions if session.completed]
    work_sessions = [session for session in completed if session.session_type == "work"]
    weekly_focus_minutes = sum(_session_minutes(session) for session in work_sessions)
    average_focus = (
        round(sum(_session_focus_score(session) for session in work_sessions) / len(work_sessions))
        if work_sessions
        else 0
    )

    _ensure_earned_achievements(user, db)
    achievements = _ordered_achievements(db)
    unlocked = db.exec(select(UserAchievement).where(UserAchievement.user_id == user.id)).all()
    unlocked_achievement_ids = {item.achievement_id for item in unlocked}
    today = user_today(user)
    today_goals = _goals_for_day(user.id, today, db)
    active_goal = next((goal for goal in today_goals if not goal.completed), None)
    today_goal_stats = _goal_stats(today_goals)

    recent_activity = [
        {
            "label": f"Completed {session.session_type} session",
            "time": session.ended_at or session.started_at,
            "type": "session_completed",
        }
        for session in sorted(completed, key=lambda item: item.ended_at or item.started_at, reverse=True)[:5]
    ]

    return {
        "weekly_focus_minutes": weekly_focus_minutes,
        "weekly_focus_hours": round(weekly_focus_minutes / 60, 1),
        "focus_score": average_focus,
        "current_streak": int(getattr(user, "current_streak", 0) or 0),
        "longest_streak": int(getattr(user, "longest_streak", 0) or 0),
        "badges_earned": len(unlocked_achievement_ids),
        "total_badges": len(achievements),
        "completed_sessions_this_week": len(completed),
        "daily_focus": _daily_focus_rows(sessions, user, 7),
        "recent_activity": recent_activity,
        "today_goals": [goal.model_dump(mode="json") for goal in today_goals],
        "active_goal": active_goal.model_dump(mode="json") if active_goal else None,
        "today_goal_stats": today_goal_stats,
    }


@router.post("/goals")
def create_study_goal(
    payload: StudyGoalCreate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    goal_day = payload.goal_date or payload.due_date or user_today(user)
    current_minutes = min(payload.current_minutes, payload.target_minutes)
    now = utc_now()
    study_goal = StudyGoal(
        user_id=user.id,
        title=payload.title.strip() or "Study",
        target_minutes=payload.target_minutes,
        current_minutes=current_minutes,
        completed=current_minutes >= payload.target_minutes,
        goal_date=goal_day,
        position=payload.position or _next_goal_position(user.id, goal_day, db),
        due_date=payload.due_date or goal_day,
        completed_at=now if current_minutes >= payload.target_minutes else None,
        updated_at=now,
    )
    db.add(study_goal)
    db.commit()
    db.refresh(study_goal)
    return study_goal.model_dump(mode="json")


@router.get("/goals")
def list_study_goals(
    goal_date: Optional[date] = None,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user.id)).all()
    if goal_date is not None:
        goals = [goal for goal in goals if _goal_day(goal) == goal_date]
    return [goal.model_dump(mode="json") for goal in sorted(goals, key=_goal_sort_key)]


@router.get("/goals/{goal_id}")
def get_study_goal(
    goal_id: int,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_goal = _get_owned_goal(goal_id, user.id, db)
    return study_goal.model_dump(mode="json")


@router.patch("/goals/{goal_id}")
def update_study_goal(
    goal_id: int,
    payload: StudyGoalUpdate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_goal = _get_owned_goal(goal_id, user.id, db)
    if payload.title is not None:
        study_goal.title = payload.title
    if payload.target_minutes is not None:
        study_goal.target_minutes = payload.target_minutes
        study_goal.current_minutes = min(study_goal.current_minutes, study_goal.target_minutes)
    if payload.current_minutes is not None:
        study_goal.current_minutes = min(payload.current_minutes, study_goal.target_minutes)
    if payload.completed is not None:
        study_goal.completed = payload.completed
        study_goal.completed_at = utc_now() if payload.completed else None
    else:
        _sync_goal_completion(study_goal)
    if payload.goal_date is not None:
        study_goal.goal_date = payload.goal_date
    if payload.position is not None:
        study_goal.position = payload.position
    if payload.due_date is not None:
        study_goal.due_date = payload.due_date
    study_goal.updated_at = utc_now()
    db.add(study_goal)
    db.commit()
    db.refresh(study_goal)
    return study_goal.model_dump(mode="json")


@router.delete("/goals/{goal_id}")
def delete_study_goal(
    goal_id: int,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_goal = _get_owned_goal(goal_id, user.id, db)
    db.delete(study_goal)
    db.commit()
    return {"message": "Study goal deleted successfully"}


@router.get("/achievements")
def list_achievements(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _ensure_earned_achievements(user, db)
    achievements = _ordered_achievements(db)
    unlocked = db.exec(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    ).all()
    unlocked_by_id = {item.achievement_id: item for item in unlocked}
    return [
        _serialize_achievement(achievement, user, db, unlocked_by_id.get(achievement.id))
        for achievement in achievements
    ]


@router.get("/achievements/unlocked")
def list_unlocked_achievements(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _ensure_earned_achievements(user, db)
    achievements = _ordered_achievements(db)
    achievements_by_id = {achievement.id: achievement for achievement in achievements}
    unlocked = db.exec(
        select(UserAchievement)
        .where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.unlocked_at.desc(), UserAchievement.id.desc())
    ).all()
    return [
        _serialize_achievement(
            achievements_by_id[user_achievement.achievement_id],
            user,
            db,
            user_achievement,
        )
        for user_achievement in unlocked
        if user_achievement.achievement_id in achievements_by_id
    ]


@router.post("/achievements/{achievement_id}/unlock")
def unlock_achievement(
    achievement_id: int,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    achievement = db.get(Achievement, achievement_id)
    if not achievement:
        raise HTTPException(status_code=404, detail="Achievement not found")

    existing = db.exec(
        select(UserAchievement).where(
            UserAchievement.user_id == user.id,
            UserAchievement.achievement_id == achievement_id,
        )
    ).first()
    if existing:
        return {
            **existing.model_dump(mode="json"),
            "achievement_title": existing.achievement_title,
        }

    user_achievement = UserAchievement(
        user_id=user.id,
        achievement_id=achievement_id,
        achievement_title=achievement.title,
    )
    db.add(user_achievement)
    db.add(
        Notification(
            user_id=user.id,
            type="achievement",
            title="Achievement unlocked",
            message=f"You unlocked {achievement.title}.",
        )
    )
    db.commit()
    db.refresh(user_achievement)
    return {
        **user_achievement.model_dump(mode="json"),
        "achievement_title": user_achievement.achievement_title,
    }


@router.get("/notifications")
def list_notifications(
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _ensure_earned_achievements(user, db)
    statement = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.read.asc(), Notification.created_at.desc(), Notification.id.desc())
    )
    if limit is not None:
        statement = statement.limit(limit)

    notifications = db.exec(statement).all()
    return [notification.model_dump(mode="json") for notification in notifications]


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    notifications = db.exec(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.read == False,  # noqa: E712
        )
    ).all()

    for notification in notifications:
        notification.read = True
        db.add(notification)

    db.commit()
    return {"updated": len(notifications)}


@router.patch("/notifications/{notification_id}")
def update_notification(
    notification_id: int,
    payload: NotificationUpdate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = payload.read
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification.model_dump(mode="json")


@router.get("/settings")
def get_user_settings(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    settings = _get_user_settings(user.id, db)
    return settings.model_dump(mode="json")


@router.put("/settings")
def update_user_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    settings = _get_user_settings(user.id, db)
    if payload.dark_mode is not None:
        settings.dark_mode = payload.dark_mode
    if payload.pomodoro_duration_minutes is not None:
        settings.pomodoro_duration_minutes = payload.pomodoro_duration_minutes
    if payload.break_duration_minutes is not None:
        settings.break_duration_minutes = payload.break_duration_minutes
    if payload.ai_persona is not None:
        settings.ai_persona = payload.ai_persona
    if payload.preferred_ai_provider is not None:
        settings.preferred_ai_provider = payload.preferred_ai_provider
    if payload.preferred_ai_model is not None:
        model = payload.preferred_ai_model.strip()
        settings.preferred_ai_model = model or None
    if payload.focus_sensitivity is not None:
        settings.focus_sensitivity = payload.focus_sensitivity
    if payload.fallback_method is not None:
        settings.fallback_method = payload.fallback_method
    if payload.notifications_enabled is not None:
        settings.notifications_enabled = payload.notifications_enabled
    if payload.focus_alerts_enabled is not None:
        settings.focus_alerts_enabled = payload.focus_alerts_enabled
    if payload.integrations is not None:
        settings.integrations = payload.integrations
    if payload.appearance is not None:
        settings.appearance = payload.appearance
    if payload.accessibility is not None:
        settings.accessibility = payload.accessibility
    if payload.privacy is not None:
        settings.privacy = payload.privacy
    settings.updated_at = utc_now()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings.model_dump(mode="json")


@router.get("/export")
def export_study_data(
    format: str = Query(default="json"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    normalized_format = format.lower()
    if normalized_format not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="format must be json or csv")

    sessions = db.exec(_user_sessions_query(user.id, start_date, end_date)).all()
    achievements = _ordered_achievements(db)
    unlocked = db.exec(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    ).all()
    unlocked_by_id = {item.achievement_id: item for item in unlocked}
    settings = _get_user_settings(user.id, db)

    if normalized_format == "json":
        quiz_attempts = db.exec(
            select(QuizAttempt).where(QuizAttempt.user_id == user.id)
        ).all()
        attempt_ids = [attempt.id for attempt in quiz_attempts if attempt.id is not None]
        quiz_attempt_answers = (
            db.exec(
                select(QuizAttemptAnswer).where(QuizAttemptAnswer.attempt_id.in_(attempt_ids))
            ).all()
            if attempt_ids
            else []
        )

        quizzes = db.exec(select(Quiz).where(Quiz.user_id == user.id)).all()
        quiz_ids = [quiz.id for quiz in quizzes if quiz.id is not None]
        quiz_questions = (
            db.exec(select(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids))).all()
            if quiz_ids
            else []
        )

        flashcard_decks = db.exec(
            select(FlashcardDeck).where(FlashcardDeck.user_id == user.id)
        ).all()
        deck_ids = [deck.id for deck in flashcard_decks if deck.id is not None]
        flashcards = (
            db.exec(select(Flashcard).where(Flashcard.deck_id.in_(deck_ids))).all()
            if deck_ids
            else []
        )
        flashcard_reviews = db.exec(
            select(FlashcardReview).where(FlashcardReview.user_id == user.id)
        ).all()

        chat_threads = db.exec(
            select(ChatThread).where(ChatThread.user_id == user.id)
        ).all()
        thread_ids = [thread.id for thread in chat_threads if thread.id is not None]
        chat_messages = (
            db.exec(select(ChatMessage).where(ChatMessage.thread_id.in_(thread_ids))).all()
            if thread_ids
            else []
        )
        message_ids = [message.id for message in chat_messages if message.id is not None]
        message_artifacts = (
            db.exec(
                select(MessageArtifact).where(MessageArtifact.message_id.in_(message_ids))
            ).all()
            if message_ids
            else []
        )

        documents = db.exec(select(Document).where(Document.user_id == user.id)).all()
        distraction_events = db.exec(
            select(DistractionEvent).where(DistractionEvent.user_id == user.id)
        ).all()
        emotion_logs = db.exec(
            select(EmotionLog).where(EmotionLog.user_id == user.id)
        ).all()
        study_goals = db.exec(select(StudyGoal).where(StudyGoal.user_id == user.id)).all()
        notifications = db.exec(
            select(Notification).where(Notification.user_id == user.id)
        ).all()

        serialized_sessions = [_session_to_dict(session) for session in sessions]
        return {
            "exported_at": utc_now().isoformat(),
            "user_id": user.id,
            "profile": _export_user_profile(user),
            "sessions": serialized_sessions,
            "study_sessions": serialized_sessions,
            "study_goals": _records_to_dict(study_goals),
            "quizzes": _records_to_dict(quizzes),
            "quiz_questions": _records_to_dict(quiz_questions),
            "quiz_attempts": _records_to_dict(quiz_attempts),
            "quiz_attempt_answers": _records_to_dict(quiz_attempt_answers),
            "flashcard_decks": _records_to_dict(flashcard_decks),
            "flashcards": _records_to_dict(flashcards),
            "flashcard_reviews": _records_to_dict(flashcard_reviews),
            "chat_threads": _records_to_dict(chat_threads),
            "chat_messages": _records_to_dict(chat_messages),
            "message_artifacts": _records_to_dict(message_artifacts),
            "documents": _records_to_dict(documents),
            "distraction_events": _records_to_dict(distraction_events),
            "emotion_logs": _records_to_dict(emotion_logs),
            "achievements": [
                _serialize_achievement(achievement, user, db, unlocked_by_id.get(achievement.id))
                for achievement in achievements
            ],
            "user_achievements": _records_to_dict(unlocked),
            "notifications": _records_to_dict(notifications),
            "settings": _settings_to_dict(settings),
        }

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "user_id",
            "session_type",
            "started_at",
            "ended_at",
            "planned_duration_minutes",
            "actual_duration_minutes",
            "completed",
            "distraction_count",
            "notes",
            "created_at",
        ],
    )
    writer.writeheader()
    for session in sessions:
        writer.writerow(
            {
                "id": session.id,
                "user_id": session.user_id,
                "session_type": session.session_type,
                "started_at": session.started_at.isoformat() if session.started_at else "",
                "ended_at": session.ended_at.isoformat() if session.ended_at else "",
                "planned_duration_minutes": session.planned_duration_minutes,
                "actual_duration_minutes": session.actual_duration_minutes or "",
                "completed": session.completed,
                "distraction_count": session.distraction_count,
                "notes": session.notes or "",
                "created_at": session.created_at.isoformat() if session.created_at else "",
            }
        )

    headers = {"Content-Disposition": 'attachment; filename="focusspark-study-export.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
