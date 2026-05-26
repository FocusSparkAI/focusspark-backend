import logging

from sqlmodel import Session, select
from app.ai.features.flashcards import flashcard_feature
from app.models.flashcard_model import FlashcardDeck, Flashcard
from app.models.chat_model import MessageArtifact, ChatMessage, ChatThread
from app.services.achievement_service import award_earned_achievements_for_user


logger = logging.getLogger(__name__)


def _award_flashcard_achievements(user_id: int, session: Session) -> None:
    try:
        award_earned_achievements_for_user(user_id, session)
    except Exception:
        session.rollback()
        logger.warning("flashcard_achievement_award_failed user_id=%s", user_id, exc_info=True)


def generate_flashcards_ai(
    content: str,
    card_count: int | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
):
    return flashcard_feature(content, card_count, provider_name=provider_name, model_name=model_name)


def _validate_flashcards(cards):
    if isinstance(cards, dict):
        if cards.get("error"):
            raise ValueError("Invalid JSON from AI while generating flashcards")

        # Accept common wrapper shapes returned by LLMs.
        for key in ("flashcards", "cards", "items", "data"):
            if isinstance(cards.get(key), list):
                cards = cards[key]
                break

    if not isinstance(cards, list):
        raise ValueError("Invalid AI flashcard payload")

    normalized = []
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("Invalid AI flashcard item")

        # Accept a few common aliases used by model outputs.
        front = card.get("front") or card.get("question") or card.get("prompt")
        back = card.get("back") or card.get("answer") or card.get("definition")
        if not isinstance(front, str) or not isinstance(back, str):
            raise ValueError("Flashcard must include string 'front' and 'back'")

        normalized.append({"front": front.strip(), "back": back.strip()})

    return normalized


# ✅ FROM TOPIC
def _is_generic_thread_title(title: str | None) -> bool:
    normalized = (title or "").strip().lower()
    return normalized in {"", "focusspark ai tutor", "ai tutor", "chat", "new chat"}


def _derive_topic(thread: ChatThread, message_content: str) -> str | None:
    if thread.title and not _is_generic_thread_title(thread.title):
        return thread.title.strip()[:255]

    try:
        from app.ai.engine import generate_text

        prompt = (
            "Provide a concise study topic (3-6 words) that summarizes the following message. "
            "Return only the topic text with no extra explanation.\n\nMessage:\n" + message_content
        )
        resp = generate_text(prompt)
        if resp:
            topic = resp.strip().splitlines()[0].strip().strip('"\'')
            if topic and not _is_generic_thread_title(topic):
                return topic[:255]
    except Exception:
        pass

    words = [word.strip(".,:;!?()[]{}\"'") for word in message_content.split()]
    words = [word for word in words if len(word) > 2]
    fallback = " ".join(words[:6]).strip()
    return fallback[:255] if fallback else None


def create_flashcards_from_topic(
    topic: str,
    user_id: int,
    session: Session,
    card_count: int | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
):
    cards = _validate_flashcards(
        generate_flashcards_ai(topic, card_count, provider_name=provider_name, model_name=model_name)
    )
    deck = FlashcardDeck(
        user_id=user_id,
        title=topic,
        topic=topic,
        source="ai"
    )
    session.add(deck)
    session.commit()
    session.refresh(deck)

    if deck.id is None:
        raise ValueError("Deck was not persisted correctly")

    created_flashcards = []
    for position, c in enumerate(cards, start=1):
        flashcard = Flashcard(
            deck_id=deck.id,
            front=c["front"],
            back=c["back"],
            position=position,
        )
        session.add(flashcard)

    deck.total_cards = len(cards)
    session.add(deck)
    session.commit()
    created_flashcards = session.exec(
        select(Flashcard)
        .where(Flashcard.deck_id == deck.id)
    ).all()
    response = {
        "deck": deck.model_dump(mode="json"),
        "flashcards": [flashcard.model_dump(mode="json") for flashcard in created_flashcards],
    }
    _award_flashcard_achievements(user_id, session)
    return response


# ✅ FROM CHAT
def create_flashcards_from_chat(message_id: int, user_id: int, session: Session):
    message = session.get(ChatMessage, message_id)

    if not message:
        raise ValueError("Message not found")

    thread = session.get(ChatThread, message.thread_id)
    if not thread:
        raise ValueError("Thread not found")
    if thread.user_id != user_id:
        raise PermissionError("You do not have access to this message")

    cards = _validate_flashcards(generate_flashcards_ai(message.content))

    # Prefer topic supplied in message.payload when available.
    derived_topic = None
    try:
        if isinstance(message.payload, dict):
            for key in ("topic", "topics", "topic_label", "label"):
                t = message.payload.get(key)
                if isinstance(t, str) and t.strip():
                    derived_topic = t.strip()
                    break
    except Exception:
        derived_topic = None

    if not derived_topic:
        derived_topic = _derive_topic(thread, message.content)

    deck = FlashcardDeck(
        user_id=user_id,
        title=derived_topic or "Chat Flashcards",
        topic=derived_topic,
        source="chat",
        created_from_message_id=message_id
    )
    session.add(deck)
    session.commit()
    session.refresh(deck)

    if deck.id is None:
        raise ValueError("Deck was not persisted correctly")

    created_flashcards = []
    for position, c in enumerate(cards, start=1):
        flashcard = Flashcard(
            deck_id=deck.id,
            front=c["front"],
            back=c["back"],
            position=position,
        )
        session.add(flashcard)

    deck.total_cards = len(cards)
    session.add(deck)
    session.commit()

    # 🔥 LINK TO CHAT
    if deck.id is None:
        raise ValueError("Deck was not persisted correctly")

    artifact = MessageArtifact(
        message_id=message_id,
        artifact_type="deck",
        artifact_id=deck.id
    )
    session.add(artifact)
    session.commit()
    created_flashcards = session.exec(
        select(Flashcard)
        .where(Flashcard.deck_id == deck.id)
    ).all()
    response = {
        "deck": deck.model_dump(mode="json"),
        "flashcards": [flashcard.model_dump(mode="json") for flashcard in created_flashcards],
    }
    _award_flashcard_achievements(user_id, session)
    return response
