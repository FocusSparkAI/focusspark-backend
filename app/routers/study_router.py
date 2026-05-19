import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.database import get_session
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
from app.utils.auth import get_current_user


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
    title: str
    target_minutes: int = PydanticField(gt=0)
    current_minutes: int = PydanticField(default=0, ge=0)
    due_date: Optional[date] = None


class StudyGoalUpdate(BaseModel):
    title: Optional[str] = None
    target_minutes: Optional[int] = PydanticField(default=None, gt=0)
    current_minutes: Optional[int] = PydanticField(default=None, ge=0)
    completed: Optional[bool] = None
    due_date: Optional[date] = None


class NotificationUpdate(BaseModel):
    read: bool = True


class UserSettingsUpdate(BaseModel):
    dark_mode: Optional[bool] = None
    pomodoro_duration_minutes: Optional[int] = PydanticField(default=None, gt=0)
    break_duration_minutes: Optional[int] = PydanticField(default=None, ge=0)
    ai_persona: Optional[str] = None
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

    return statement.order_by(text("started_at DESC, id DESC"))


def _achievement_window_start(achievement: Achievement) -> Optional[datetime]:
    if achievement.criteria_window_days is None:
        return None
    return datetime.utcnow() - timedelta(days=achievement.criteria_window_days)


def _compute_achievement_progress(
    achievement: Achievement,
    user,
    db: Session,
) -> tuple[int, int]:
    target = max(achievement.criteria_target or 1, 1)
    metric = (achievement.criteria_type or "sessions_completed").lower()
    window_start = _achievement_window_start(achievement)

    sessions_statement = select(StudySession).where(StudySession.user_id == user.id)
    if window_start is not None:
        sessions_statement = sessions_statement.where(StudySession.started_at >= window_start)
    sessions = db.exec(sessions_statement).all()

    if metric in {"sessions_completed", "completed_sessions"}:
        current = sum(1 for session in sessions if session.completed)
    elif metric in {"work_sessions_completed", "work_sessions"}:
        current = sum(1 for session in sessions if session.completed and session.session_type == "work")
    elif metric in {"focus_minutes", "study_minutes"}:
        current = sum(
            session.actual_duration_minutes or session.planned_duration_minutes
            for session in sessions
            if session.completed and session.session_type == "work"
        )
    elif metric in {"distraction_free_sessions", "zero_distraction_sessions"}:
        current = sum(1 for session in sessions if session.completed and (session.distraction_count or 0) == 0)
    elif metric in {"streak_days", "current_streak"}:
        current = int(getattr(user, "current_streak", 0) or 0)
    elif metric == "total_focus_minutes":
        current = int(getattr(user, "total_focus_minutes", 0) or 0)
    else:
        current = 0

    return current, target


def _serialize_achievement(
    achievement: Achievement,
    user,
    db: Session,
    user_achievement: Optional[UserAchievement] = None,
) -> dict:
    current, target = _compute_achievement_progress(achievement, user, db)
    unlocked = user_achievement is not None

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
    }


def _session_to_dict(session: StudySession) -> dict:
    return session.model_dump(mode="json")


def _settings_to_dict(settings: UserSettings) -> dict:
    return settings.model_dump(mode="json")


@router.post("/sessions")
def create_study_session(
    payload: StudySessionCreate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_session = StudySession(
        user_id=user.id,
        session_type=payload.session_type,
        started_at=payload.started_at or datetime.utcnow(),
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
    study_session.ended_at = payload.ended_at or datetime.utcnow()
    study_session.actual_duration_minutes = payload.actual_duration_minutes
    if payload.distraction_count is not None:
        study_session.distraction_count = payload.distraction_count
    study_session.completed = True
    if payload.notes is not None:
                study_session.notes = payload.notes
    db.add(study_session)
    db.commit()
    db.refresh(study_session)
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
        detected_at=payload.detected_at or datetime.utcnow(),
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
        detected_at=payload.detected_at or datetime.utcnow(),
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
        .order_by(text("started_at DESC, id DESC"))
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
    }


@router.post("/goals")
def create_study_goal(
    payload: StudyGoalCreate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    study_goal = StudyGoal(
        user_id=user.id,
        title=payload.title,
        target_minutes=payload.target_minutes,
        current_minutes=payload.current_minutes,
        due_date=payload.due_date,
    )
    db.add(study_goal)
    db.commit()
    db.refresh(study_goal)
    return study_goal.model_dump(mode="json")


@router.get("/goals")
def list_study_goals(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    goals = db.exec(
        select(StudyGoal)
        .where(StudyGoal.user_id == user.id)
        .order_by(text("completed ASC, due_date ASC, id DESC"))
    ).all()
    return [goal.model_dump(mode="json") for goal in goals]


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
    if payload.current_minutes is not None:
        study_goal.current_minutes = payload.current_minutes
    if payload.completed is not None:
        study_goal.completed = payload.completed
    if payload.due_date is not None:
        study_goal.due_date = payload.due_date
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
    achievements = db.exec(select(Achievement).order_by(text("id ASC"))).all()
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
    achievements = db.exec(select(Achievement).order_by(text("id ASC"))).all()
    achievements_by_id = {achievement.id: achievement for achievement in achievements}
    unlocked = db.exec(
        select(UserAchievement)
        .where(UserAchievement.user_id == user.id)
        .order_by(text("unlocked_at DESC, id DESC"))
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
    db.commit()
    db.refresh(user_achievement)
    return {
        **user_achievement.model_dump(mode="json"),
        "achievement_title": user_achievement.achievement_title,
    }


@router.get("/notifications")
def list_notifications(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    notifications = db.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(text("read ASC, created_at DESC, id DESC"))
    ).all()
    return [notification.model_dump(mode="json") for notification in notifications]


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
    settings.updated_at = datetime.utcnow()
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
    achievements = db.exec(select(Achievement).order_by(text("id ASC"))).all()
    unlocked = db.exec(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    ).all()
    unlocked_by_id = {item.achievement_id: item for item in unlocked}
    settings = _get_user_settings(user.id, db)

    if normalized_format == "json":
        return {
            "exported_at": datetime.utcnow().isoformat(),
            "user_id": user.id,
            "sessions": [_session_to_dict(session) for session in sessions],
            "achievements": [
                _serialize_achievement(achievement, user, db, unlocked_by_id.get(achievement.id))
                for achievement in achievements
            ],
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