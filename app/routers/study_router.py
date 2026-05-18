from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
    notifications_enabled: Optional[bool] = None
    focus_alerts_enabled: Optional[bool] = None


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
def list_achievements(db: Session = Depends(get_session)):
    achievements = db.exec(select(Achievement).order_by(text("id ASC"))).all()
    return [achievement.model_dump(mode="json") for achievement in achievements]


@router.get("/achievements/unlocked")
def list_unlocked_achievements(
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    unlocked = db.exec(
        select(UserAchievement)
        .where(UserAchievement.user_id == user.id)
        .order_by(text("unlocked_at DESC, id DESC"))
    ).all()
    return [user_achievement.model_dump(mode="json") for user_achievement in unlocked]


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
        return existing.model_dump(mode="json")

    user_achievement = UserAchievement(user_id=user.id, achievement_id=achievement_id)
    db.add(user_achievement)
    db.commit()
    db.refresh(user_achievement)
    return user_achievement.model_dump(mode="json")


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
    if payload.notifications_enabled is not None:
        settings.notifications_enabled = payload.notifications_enabled
    if payload.focus_alerts_enabled is not None:
        settings.focus_alerts_enabled = payload.focus_alerts_enabled
    settings.updated_at = datetime.utcnow()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings.model_dump(mode="json")