from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session
from app.db.database import get_session
from sqlmodel import select
from app.models.flashcard_model import FlashcardDeck, Flashcard, FlashcardReview
from app.models.productivity_model import UserSettings
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
from app.utils.timezone import utc_now


router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


def _get_ai_defaults(user_id: int, session: Session) -> tuple[str | None, str | None]:
    settings = session.exec(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).first()
    if not settings:
        return None, None
    return settings.preferred_ai_provider, settings.preferred_ai_model


class FlashcardDeckReviewItem(BaseModel):
    flashcard_id: int
    known: bool
    correct_count: int = PydanticField(default=0, ge=0)
    incorrect_count: int = PydanticField(default=0, ge=0)


class FlashcardDeckReviewComplete(BaseModel):
    reviews: list[FlashcardDeckReviewItem]


@router.get("/")
def get_all_decks(
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    decks = session.exec(
        select(FlashcardDeck).where(FlashcardDeck.user_id == user.id)
    ).all()
    if not decks:
        return []

    response = []
    for deck in decks:
        deck_data = deck.model_dump(mode="json")
        flashcards = session.exec(
            select(Flashcard).where(Flashcard.deck_id == deck.id)
        ).all()
        card_ids = [flashcard.id for flashcard in flashcards if flashcard.id is not None]
        reviews = (
            session.exec(
                select(FlashcardReview).where(
                    FlashcardReview.user_id == user.id,
                    FlashcardReview.flashcard_id.in_(card_ids),
                )
            ).all()
            if card_ids
            else []
        )

        total_cards = deck.total_cards or len(flashcards)
        total_correct = sum(review.correct_count for review in reviews)
        total_incorrect = sum(review.incorrect_count for review in reviews)
        total_attempts = total_correct + total_incorrect
        latest_known = sum(1 for review in reviews if review.known)
        reviewed_count = sum(1 for review in reviews if review.last_reviewed_at is not None)
        last_reviewed = max(
            (review.last_reviewed_at for review in reviews if review.last_reviewed_at is not None),
            default=None,
        )

        deck_data.update(
            {
                "progress": round((latest_known / total_cards) * 100) if total_cards else 0,
                "accuracy": round((total_correct / total_attempts) * 100) if total_attempts else 0,
                "review_count": reviewed_count,
                "last_reviewed": last_reviewed,
            }
        )
        response.append(deck_data)

    return response


@router.get("/reviews")
def get_flashcard_reviews(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    reviews = session.exec(
        select(FlashcardReview)
        .where(FlashcardReview.user_id == user.id)
        .order_by(FlashcardReview.next_review_at.asc(), FlashcardReview.id.desc())
    ).all()
    return [review.model_dump(mode="json") for review in reviews]


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

    flashcards = session.exec(
        select(Flashcard).where(Flashcard.deck_id == deck_id)
    ).all()
    card_ids = [flashcard.id for flashcard in flashcards if flashcard.id is not None]
    reviews = (
        session.exec(
            select(FlashcardReview).where(
                FlashcardReview.user_id == user.id,
                FlashcardReview.flashcard_id.in_(card_ids),
            )
        ).all()
        if card_ids
        else []
    )
    reviews_by_card_id = {review.flashcard_id: review for review in reviews}

    response = []
    for flashcard in flashcards:
        card_data = flashcard.model_dump(mode="json")
        review = reviews_by_card_id.get(flashcard.id)
        if review:
            card_data.update(
                {
                    "correct_count": review.correct_count,
                    "incorrect_count": review.incorrect_count,
                    "last_reviewed": review.last_reviewed_at,
                    "known": review.known,
                }
            )
        response.append(card_data)

    return response


@router.post("/generate", response_model=FlashcardBundleResponse)
def generate_flashcards(data: FlashcardGenerate,
                        session: Session = Depends(get_session),
                        user=Depends(get_current_user)):
    try:
        provider_name, model_name = _get_ai_defaults(user.id, session)
        return create_flashcards_from_topic(
            data.topic,
            user.id,
            session,
            data.card_count,
            provider_name=provider_name,
            model_name=model_name,
        )
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


@router.put("/{deck_id}/review-complete")
def complete_flashcard_deck_review(
    deck_id: int,
    payload: FlashcardDeckReviewComplete,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    deck = session.exec(
        select(FlashcardDeck).where(
            FlashcardDeck.id == deck_id,
            FlashcardDeck.user_id == user.id,
        )
    ).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    if not payload.reviews:
        raise HTTPException(status_code=400, detail="No reviews submitted")

    flashcards = session.exec(
        select(Flashcard).where(Flashcard.deck_id == deck_id)
    ).all()
    owned_card_ids = {flashcard.id for flashcard in flashcards if flashcard.id is not None}

    submitted_card_ids = [item.flashcard_id for item in payload.reviews]
    if len(submitted_card_ids) != len(set(submitted_card_ids)):
        raise HTTPException(status_code=400, detail="Duplicate flashcard reviews submitted")

    if any(card_id not in owned_card_ids for card_id in submitted_card_ids):
        raise HTTPException(status_code=400, detail="Review contains a card outside this deck")

    existing_reviews = session.exec(
        select(FlashcardReview).where(
            FlashcardReview.user_id == user.id,
            FlashcardReview.flashcard_id.in_(submitted_card_ids),
        )
    ).all()
    reviews_by_card_id = {review.flashcard_id: review for review in existing_reviews}

    now = utc_now()
    updated_reviews = []
    for item in payload.reviews:
        review = reviews_by_card_id.get(item.flashcard_id)
        if review is None:
            review = FlashcardReview(
                user_id=user.id,
                flashcard_id=item.flashcard_id,
            )

        review.known = item.known
        review.correct_count += item.correct_count
        review.incorrect_count += item.incorrect_count
        review.repetitions += 1
        review.last_reviewed_at = now

        if item.known:
            review.review_interval_days = max(1, review.review_interval_days * 2)
            review.ease_factor = min(3.0, review.ease_factor + 0.1)
        else:
            review.review_interval_days = 1
            review.ease_factor = max(1.3, review.ease_factor - 0.2)

        review.next_review_at = now + timedelta(days=review.review_interval_days)
        session.add(review)
        updated_reviews.append(review)

    session.commit()
    for review in updated_reviews:
        session.refresh(review)

    return [review.model_dump(mode="json") for review in updated_reviews]
