import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.ai.features.focus_emotion import DetectionSmoother, analyze_frame, decode_base64_image


router = APIRouter(tags=["Focus"])


class FocusFrameRequest(BaseModel):
    image: str


def _build_invalid_image_response():
    return {
        "emotion": "Neutral",
        "focused": False,
        "metrics": {"reason": "invalid_image"},
    }


@router.post("/analyze")
def analyze_focus_frame(payload: FocusFrameRequest):
    img = decode_base64_image(payload.image)
    if img is None:
        return _build_invalid_image_response()

    return analyze_frame(img)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    smoother = DetectionSmoother(window_size=7)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if "image" not in message:
                await websocket.send_text(json.dumps({"error": "image_required"}))
                continue

            img = decode_base64_image(message["image"])
            if img is None:
                await websocket.send_text(json.dumps(_build_invalid_image_response()))
                continue

            result = analyze_frame(img)
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

    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({"error": "invalid_json"}))
    except WebSocketDisconnect:
        print("Client disconnected")