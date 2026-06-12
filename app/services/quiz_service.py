import logging
import random

from sqlmodel import Session, select
from app.ai.features.quiz import quiz_feature
from app.models.quiz_model import Quiz, QuizQuestion, QuizDifficulty
from app.models.chat_model import MessageArtifact, ChatMessage, ChatThread
from app.services.achievement_service import award_earned_achievements_for_user


DEFAULT_CHAT_QUIZ_DIFFICULTY = QuizDifficulty.BEGINNER
logger = logging.getLogger(__name__)


def _shuffle_options(options: list[str], correct_answer_index: int) -> tuple[list[str], int]:
    correct_answer = options[correct_answer_index]
    shuffled_options = options[:]
    random.shuffle(shuffled_options)
    return shuffled_options, shuffled_options.index(correct_answer)


def _award_quiz_achievements(user_id: int, session: Session) -> None:
    try:
        award_earned_achievements_for_user(user_id, session)
    except Exception:
        session.rollback()
        logger.warning("quiz_achievement_award_failed user_id=%s", user_id, exc_info=True)


def generate_quiz_ai(
    content: str,
    difficulty: QuizDifficulty,
    provider_name: str | None = None,
    model_name: str | None = None,
):
    return quiz_feature(content, difficulty, provider_name=provider_name, model_name=model_name)


def _validate_quiz_questions(questions):
    if isinstance(questions, dict):
        for key in ("questions", "quiz", "items"):
            maybe_questions = questions.get(key)
            if isinstance(maybe_questions, list):
                questions = maybe_questions
                break

    if not isinstance(questions, list):
        raise ValueError("Invalid AI quiz payload")

    normalized = []
    for q in questions:
        if not isinstance(q, dict):
            raise ValueError("Invalid AI quiz item")

        question_text = q.get("question")
        options = q.get("options")
        answer_index = q.get("correct_answer_index")
        explanation = q.get("explanation")

        if not isinstance(question_text, str):
            raise ValueError("Quiz item must include string 'question'")
        if not isinstance(options, list) or not all(isinstance(opt, str) for opt in options):
            raise ValueError("Quiz item must include string list 'options'")
        if explanation is not None and not isinstance(explanation, str):
            explanation = None

        # Normalize common AI aliases to canonical zero-based index.
        if not isinstance(answer_index, int):
            for alias in ("correctAnswerIndex", "answer_index", "answerIndex"):
                alias_value = q.get(alias)
                if isinstance(alias_value, int):
                    answer_index = alias_value
                    break

        if not isinstance(answer_index, int):
            answer_value = q.get("answer")
            if isinstance(answer_value, int):
                answer_index = answer_value
            elif isinstance(answer_value, str):
                normalized_options = [opt.strip().lower() for opt in options]
                normalized_answer = answer_value.strip().lower()

                if normalized_answer in normalized_options:
                    answer_index = normalized_options.index(normalized_answer)
                elif len(normalized_answer) == 1 and normalized_answer in "abcd":
                    answer_index = ord(normalized_answer) - ord("a")

        if not isinstance(answer_index, int):
            raise ValueError("Quiz item must include int 'correct_answer_index'")
        if answer_index < 0 or answer_index >= len(options):
            raise ValueError("'correct_answer_index' is out of range for options")

        options, answer_index = _shuffle_options(options, answer_index)

        normalized.append(
            {
                "question": question_text,
                "options": options,
                "correct_answer_index": answer_index,
                "explanation": explanation.strip() if explanation else None,
            }
        )

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


def create_quiz_from_topic(
    topic: str,
    user_id: int,
    session: Session,
    difficulty: QuizDifficulty,
    provider_name: str | None = None,
    model_name: str | None = None,
):
    questions = _validate_quiz_questions(
        generate_quiz_ai(topic, difficulty, provider_name=provider_name, model_name=model_name)
    )
    quiz = Quiz(
        user_id=user_id,
        title=topic,
        topic=topic,
        difficulty=difficulty,
        source="ai"
    )
    session.add(quiz)
    session.commit()
    session.refresh(quiz)

    if quiz.id is None:
        raise ValueError("Quiz was not persisted correctly")

    created_questions = []
    for position, q in enumerate(questions, start=1):
        question = QuizQuestion(
            quiz_id=quiz.id,
            question=q["question"],
            options=q["options"],
            correct_answer_index=q["correct_answer_index"],
            explanation=q.get("explanation"),
            position=position,
        )
        session.add(question)

    quiz.total_questions = len(questions)
    session.add(quiz)
    session.commit()
    created_questions = session.exec(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.position.asc(), QuizQuestion.id.asc())
    ).all()
    response = {
        "quiz": quiz.model_dump(mode="json"),
        "questions": [
            question.model_dump(mode="json")
            for question in created_questions
        ],
    }
    _award_quiz_achievements(user_id, session)
    return response


# ✅ FROM CHAT
def create_quiz_from_chat(message_id: int, user_id: int, session: Session):
    message = session.get(ChatMessage, message_id)

    if not message:
        raise ValueError("Message not found")

    thread = session.get(ChatThread, message.thread_id)
    if not thread:
        raise ValueError("Thread not found")
    if thread.user_id != user_id:
        raise PermissionError("You do not have access to this message")

    questions = _validate_quiz_questions(
        generate_quiz_ai(message.content, DEFAULT_CHAT_QUIZ_DIFFICULTY)
    )

    # Prefer topic already present in message.payload if provided by the client.
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

    # Otherwise fall back to thread title or AI-assisted extraction.
    if not derived_topic:
        derived_topic = _derive_topic(thread, message.content)

    quiz = Quiz(
        user_id=user_id,
        title=derived_topic or "Chat Quiz",
        topic=derived_topic,
        difficulty=DEFAULT_CHAT_QUIZ_DIFFICULTY,
        source="chat",
        created_from_message_id=message_id
    )
    session.add(quiz)
    session.commit()
    session.refresh(quiz)

    if quiz.id is None:
        raise ValueError("Quiz was not persisted correctly")

    created_questions = []
    for position, q in enumerate(questions, start=1):
        question = QuizQuestion(
            quiz_id=quiz.id,
            question=q["question"],
            options=q["options"],
            correct_answer_index=q["correct_answer_index"],
            explanation=q.get("explanation"),
            topic=derived_topic,
            position=position,
        )
        session.add(question)

    quiz.total_questions = len(questions)
    session.add(quiz)
    session.commit()

    # 🔥 LINK
    artifact = MessageArtifact(
        message_id=message_id,
        artifact_type="quiz",
        artifact_id=quiz.id
    )
    session.add(artifact)
    session.commit()
    created_questions = session.exec(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.position.asc(), QuizQuestion.id.asc())
    ).all()
    response = {
        "quiz": quiz.model_dump(mode="json"),
        "questions": [
            question.model_dump(mode="json")
            for question in created_questions
        ],
    }
    _award_quiz_achievements(user_id, session)
    return response
