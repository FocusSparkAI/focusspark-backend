from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from sqlmodel import Session
from app.db.database import get_session
from sqlmodel import select
from app.models.chat_model import ChatThread, ChatMessage, MessageArtifact
from app.models.flashcard_model import FlashcardDeck, Flashcard
from app.models.quiz_model import Quiz, QuizQuestion
from app.schemas.chat_schema import ChatRequest, CreateThreadRequest
from app.services.chat_service import handle_chat, handle_document_chat, create_thread
from app.utils.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Chat"])


def _hydrate_artifact(artifact: MessageArtifact, user_id: int, session: Session):
    base = {
        "id": artifact.id,
        "artifact_type": artifact.artifact_type,
        "artifact_id": artifact.artifact_id,
    }

    if artifact.artifact_type == "deck":
        deck = session.exec(
            select(FlashcardDeck).where(
                FlashcardDeck.id == artifact.artifact_id,
                FlashcardDeck.user_id == user_id,
            )
        ).first()
        if not deck:
            return None

        cards = session.exec(
            select(Flashcard)
            .where(Flashcard.deck_id == deck.id)
            .order_by(Flashcard.position.asc(), Flashcard.id.asc())
        ).all()
        return {
            **base,
            "deck_id": deck.id,
            "title": deck.title,
            "topic": deck.topic,
            "source": deck.source,
            "total_cards": deck.total_cards or len(cards),
            "created_from_message_id": deck.created_from_message_id,
            "cards": [card.model_dump(mode="json") for card in cards],
            "flashcards": [card.model_dump(mode="json") for card in cards],
        }

    if artifact.artifact_type == "quiz":
        quiz = session.exec(
            select(Quiz).where(
                Quiz.id == artifact.artifact_id,
                Quiz.user_id == user_id,
            )
        ).first()
        if not quiz:
            return None

        questions = session.exec(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.position.asc(), QuizQuestion.id.asc())
        ).all()
        return {
            **base,
            "quiz_id": quiz.id,
            "title": quiz.title,
            "topic": quiz.topic,
            "source": quiz.source,
            "difficulty": quiz.difficulty,
            "total_questions": quiz.total_questions or len(questions),
            "created_from_message_id": quiz.created_from_message_id,
            "questions": [question.model_dump(mode="json") for question in questions],
        }

    return base


@router.get("/threads")
def get_threads(
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    return session.exec(
        select(ChatThread)
        .where(ChatThread.user_id == user.id)
        .order_by(ChatThread.created_at.desc())
    ).all()


@router.post("/threads")
def create_chat_thread(
    data: CreateThreadRequest,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    thread = create_thread(
        data.title.strip() if data.title else None,
        user.id,
        session,
        ai_provider=data.ai_provider,
    )
    return thread


@router.get("/threads/{thread_id}")
def get_messages(
    thread_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    thread = session.exec(
        select(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.user_id == user.id,
        )
    ).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return session.exec(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()


@router.get("/message/{message_id}/artifacts")
def get_artifacts(
    message_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    message = session.get(ChatMessage, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    thread = session.get(ChatThread, message.thread_id)
    if not thread or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Message not found")

    artifacts = session.exec(
        select(MessageArtifact).where(MessageArtifact.message_id == message_id)
    ).all()
    return [
        hydrated
        for artifact in artifacts
        if (hydrated := _hydrate_artifact(artifact, user.id, session)) is not None
    ]


@router.post("/")
def chat(data: ChatRequest,
         session: Session = Depends(get_session),
         user=Depends(get_current_user)):
    try:
        ai_msg = handle_chat(data.message, data.thread_id, user.id, session)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {e}")

    return {
        "response": ai_msg.content,
        "message_id": ai_msg.id
    }


@router.post("/document")
async def chat_with_document(
    thread_id: int = Form(...),
    message: str = Form("Explain this document."),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    try:
        file_bytes = await file.read()
        ai_msg = handle_document_chat(
            message=message,
            thread_id=thread_id,
            user_id=user.id,
            session=session,
            file_name=file.filename or "document",
            content_type=file.content_type,
            file_bytes=file_bytes,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document chat failed: {e}")

    return {
        "response": ai_msg.content,
        "message_id": ai_msg.id,
    }

