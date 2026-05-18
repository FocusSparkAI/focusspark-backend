from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import text
from sqlmodel import Session
from app.db.database import get_session
from sqlmodel import select
from app.models.flashcard_model import FlashcardDeck, Flashcard, FlashcardReview
from app.schemas.flashcard_schema import (
    FlashcardGenerate,
    FlashcardFromChat,
    FlashcardBundleResponse,
)
from app.services.flashcard_service import (
    create_flashcards_from_topic,
    create_flashcards_from_chat
)
from app.utils.auth import get_current_user


router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


class FlashcardReviewUpdate(BaseModel):
    known: bool
    correct_count: int = PydanticField(default=0, ge=0)
    incorrect_count: int = PydanticField(default=0, ge=0)


def _get_owned_flashcard(flashcard_id: int, user_id: int, session: Session) -> Flashcard:
    flashcard = session.get(Flashcard, flashcard_id)
    if not flashcard:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    deck = session.get(FlashcardDeck, flashcard.deck_id)
    if not deck or deck.user_id != user_id:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    return flashcard


@router.get("/")
def get_all_decks(
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    return session.exec(
        select(FlashcardDeck).where(FlashcardDeck.user_id == user.id)
    ).all()


@router.get("/{deck_id}")
def get_flashcards(
    deck_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    deck = session.exec(
        select(FlashcardDeck).where(
            FlashcardDeck.id == deck_id,
            FlashcardDeck.user_id == user.id,
        )
    ).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    return session.exec(
        select(Flashcard).where(Flashcard.deck_id == deck_id)
    ).all()


@router.post("/generate", response_model=FlashcardBundleResponse)
def generate_flashcards(data: FlashcardGenerate,
                        session: Session = Depends(get_session),
                        user=Depends(get_current_user)):
    try:
        return create_flashcards_from_topic(data.topic, user.id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI provider error: {e}")


@router.post("/from-chat", response_model=FlashcardBundleResponse)
def flashcards_from_chat(data: FlashcardFromChat,
                         session: Session = Depends(get_session),
                         user=Depends(get_current_user)):
    try:
        return create_flashcards_from_chat(data.message_id, user.id, session)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI provider error: {e}")


@router.get("/reviews")
def get_flashcard_reviews(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    reviews = session.exec(
        select(FlashcardReview)
        .where(FlashcardReview.user_id == user.id)
        .order_by(text("next_review_at ASC, id DESC"))
    ).all()
    return [review.model_dump(mode="json") for review in reviews]


@router.put("/{flashcard_id}/review")
def upsert_flashcard_review(
    flashcard_id: int,
    payload: FlashcardReviewUpdate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    flashcard = _get_owned_flashcard(flashcard_id, user.id, session)
    flashcard_pk = flashcard.id
    if flashcard_pk is None:
        raise HTTPException(status_code=500, detail="Flashcard is invalid")
    review = session.exec(
        select(FlashcardReview).where(
            FlashcardReview.user_id == user.id,
            FlashcardReview.flashcard_id == flashcard_pk,
        )
    ).first()

    now = datetime.utcnow()
    if review is None:
        review = FlashcardReview(
            user_id=user.id,
            flashcard_id=flashcard_pk,
        )

    review.known = payload.known
    review.correct_count += payload.correct_count
    review.incorrect_count += payload.incorrect_count
    review.repetitions += 1
    review.last_reviewed_at = now

    if payload.known:
        review.review_interval_days = max(1, review.review_interval_days * 2)
        review.ease_factor = min(3.0, review.ease_factor + 0.1)
    else:
        review.review_interval_days = 1
        review.ease_factor = max(1.3, review.ease_factor - 0.2)

    review.next_review_at = now + timedelta(days=review.review_interval_days)
    session.add(review)
    session.commit()
    session.refresh(review)
    return review.model_dump(mode="json")