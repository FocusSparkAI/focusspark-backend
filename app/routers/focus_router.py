import json
import logging
import time

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from pydantic import BaseModel
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.ai.features.focus_emotion import (
    DetectionSmoother,
    EMOTION_INTERVAL_SECONDS,
    analyze_frame,
    decode_base64_image,
)
from app.db.database import engine
from app.utils.auth import get_current_user, resolve_user_from_token


router = APIRouter(tags=["Focus"])
logger = logging.getLogger(__name__)


class FocusFrameRequest(BaseModel):
    image: str


def _build_invalid_image_response():
    return {
        "emotion": "Neutral",
        "focused": False,
        "metrics": {"reason": "invalid_image"},
    }


@router.post("/analyze")
def analyze_focus_frame(payload: FocusFrameRequest, user=Depends(get_current_user)):
    img = decode_base64_image(payload.image)
    if img is None:
        return _build_invalid_image_response()

    return analyze_frame(img)


def _authenticate_websocket_token(token: str | None):
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    try:
        with Session(engine) as session:
            return resolve_user_from_token(token, session)
    except Exception as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(default=None)):
    _authenticate_websocket_token(token)
    await websocket.accept()
    smoother = DetectionSmoother(window_size=7)
    last_emotion = "Neutral"
    last_emotion_at = 0.0

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "invalid_json"}))
                continue

            if "image" not in message:
                await websocket.send_text(json.dumps({"error": "image_required"}))
                continue

            img = decode_base64_image(message["image"])
            if img is None:
                await websocket.send_text(json.dumps(_build_invalid_image_response()))
                continue

            now = time.monotonic()
            should_detect_emotion = (
                last_emotion_at == 0.0
                or (now - last_emotion_at) >= EMOTION_INTERVAL_SECONDS
            )

            result = await run_in_threadpool(
                analyze_frame,
                img,
                detect_emotion=should_detect_emotion,
                fallback_emotion=last_emotion,
            )
            if result["metrics"].get("emotion_analyzed"):
                last_emotion = result["emotion"]
                last_emotion_at = now

            stable_emotion, stable_focus = smoother.update(
                result["emotion"], result["focused"]
            )

            await websocket.send_text(
                json.dumps(
                    {
                        "emotion": stable_emotion,
                        "focused": stable_focus,
                        "metrics": result["metrics"],
                    }
                )
            )

    except WebSocketDisconnect:
        logger.info("focus_websocket_disconnected")
