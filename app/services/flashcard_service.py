from sqlmodel import Session, select
from app.ai.features.flashcards import flashcard_feature
from app.models.flashcard_model import FlashcardDeck, Flashcard
from app.models.chat_model import MessageArtifact, ChatMessage, ChatThread


def generate_flashcards_ai(content: str):
    return flashcard_feature(content)


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
def create_flashcards_from_topic(topic: str, user_id: int, session: Session):
    cards = _validate_flashcards(generate_flashcards_ai(topic))
    deck = FlashcardDeck(
        user_id=user_id,
        title=f"{topic} Flashcards",
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
    return {
        "deck": deck.model_dump(mode="json"),
        "flashcards": [flashcard.model_dump(mode="json") for flashcard in created_flashcards],
    }


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
    deck = FlashcardDeck(
        user_id=user_id,
        title="Chat Flashcards",
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
    return {
        "deck": deck.model_dump(mode="json"),
        "flashcards": [flashcard.model_dump(mode="json") for flashcard in created_flashcards],
    }
