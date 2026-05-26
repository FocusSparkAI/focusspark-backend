from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session
from app.db.database import get_session
from sqlmodel import select
from app.models.quiz_model import Quiz, QuizAttempt, QuizAttemptAnswer, QuizQuestion
from app.models.productivity_model import UserSettings
from app.schemas.quiz_schema import QuizGenerate, QuizFromChat, QuizBundleResponse
from app.services.quiz_service import (
    create_quiz_from_topic,
    create_quiz_from_chat
)
from app.utils.auth import get_current_user


router = APIRouter(prefix="/quiz", tags=["Quiz"])


def _get_ai_defaults(user_id: int, session: Session) -> tuple[str | None, str | None]:
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()
    if not settings:
        return None, None
    return settings.preferred_ai_provider, settings.preferred_ai_model


class QuizAttemptAnswerInput(BaseModel):
    question_id: int
    selected_answer_index: int | None = None


class QuizAttemptCreate(BaseModel):
    answers: list[QuizAttemptAnswerInput] = []
    started_at: datetime | None = None
    completed_at: datetime | None = None
    time_taken_seconds: int | None = PydanticField(default=None, ge=0)


def _get_owned_quiz(quiz_id: int, user_id: int, session: Session) -> Quiz:
    quiz = session.exec(
        select(Quiz).where(
            Quiz.id == quiz_id,
            Quiz.user_id == user_id,
        )
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


def _get_owned_quiz_questions(quiz_id: int, user_id: int, session: Session):
    _get_owned_quiz(quiz_id, user_id, session)
    return session.exec(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.position.asc(), QuizQuestion.id.asc())
    ).all()


@router.get("/")
def get_all_quizzes(
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    quizzes = session.exec(
        select(Quiz).where(Quiz.user_id == user.id)
    ).all()

    results = []
    for quiz in quizzes:
        attempts = session.exec(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.user_id == user.id,
            )
        ).all()
        percentages = [float(attempt.percentage or 0) for attempt in attempts]
        last_attempt = max(
            attempts,
            key=lambda attempt: attempt.completed_at or attempt.created_at,
            default=None,
        )
        data = quiz.model_dump(mode="json")
        data["total_attempts"] = len(attempts)
        data["best_score"] = round(max(percentages)) if percentages else 0
        data["average_score"] = round(sum(percentages) / len(percentages)) if percentages else 0
        data["last_attempted"] = (
            (last_attempt.completed_at or last_attempt.created_at).isoformat()
            if last_attempt
            else None
        )
        results.append(data)

    return results

@router.get("/{quiz_id}")
def get_quiz_questions(
    quiz_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    return _get_owned_quiz_questions(quiz_id, user.id, session)


@router.get("/{quiz_id}/questions")
def get_quiz_questions_alias(
    quiz_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    return _get_owned_quiz_questions(quiz_id, user.id, session)


@router.get("/{quiz_id}/items")
def get_quiz_items_alias(
    quiz_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    return _get_owned_quiz_questions(quiz_id, user.id, session)


@router.post("/generate", response_model=QuizBundleResponse)
def generate_quiz(data: QuizGenerate,
                  session: Session = Depends(get_session),
                  user=Depends(get_current_user)):
    try:
        provider_name, model_name = _get_ai_defaults(user.id, session)
        return create_quiz_from_topic(
            data.topic,
            user.id,
            session,
            data.difficulty,
            provider_name=provider_name,
            model_name=model_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI provider error: {e}")


@router.post("/from-chat", response_model=QuizBundleResponse)
def quiz_from_chat(data: QuizFromChat,
                   session: Session = Depends(get_session),
                   user=Depends(get_current_user)):
    try:
        return create_quiz_from_chat(data.message_id, user.id, session)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI provider error: {e}")


@router.get("/{quiz_id}/attempts")
def get_quiz_attempts(
    quiz_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _get_owned_quiz(quiz_id, user.id, session)
    attempts = session.exec(
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
    ).all()
    return [attempt.model_dump(mode="json") for attempt in attempts]


@router.post("/{quiz_id}/attempts")
def submit_quiz_attempt(
    quiz_id: int,
    payload: QuizAttemptCreate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    quiz = _get_owned_quiz(quiz_id, user.id, session)
    questions = session.exec(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.position.asc(), QuizQuestion.id.asc())
    ).all()
    question_map = {question.id: question for question in questions if question.id is not None}

    total_questions = quiz.total_questions or len(questions)
    score = 0
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=user.id,
        score=0,
        total_questions=total_questions,
        percentage=0.0,
        passed=False,
        started_at=payload.started_at or datetime.utcnow(),
        completed_at=payload.completed_at or datetime.utcnow(),
        time_taken_seconds=payload.time_taken_seconds,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    attempt_id = attempt.id
    if attempt_id is None:
        raise HTTPException(status_code=500, detail="Quiz attempt was not saved")

    for answer in payload.answers:
        question = question_map.get(answer.question_id)
        if not question:
            continue

        question_id = question.id
        if question_id is None:
            continue

        is_correct = answer.selected_answer_index == question.correct_answer_index
        if is_correct:
            score += 1

        attempt_answer = QuizAttemptAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_answer_index=answer.selected_answer_index,
            is_correct=is_correct,
        )
        session.add(attempt_answer)

    attempt.score = score
    attempt.total_questions = total_questions
    attempt.percentage = round((score / total_questions) * 100, 2) if total_questions else 0.0
    attempt.passed = attempt.percentage >= quiz.passing_score
    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    return {
        "attempt": attempt.model_dump(mode="json"),
        "answers_submitted": len(payload.answers),
    }
