import base64
import os
import threading
from collections import Counter, deque

import cv2
import mediapipe as mp
import numpy as np
from deepface import DeepFace


_FACE_DETECTION = mp.solutions.face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.6
)
_FACE_MESH = mp.solutions.face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6,
)
_MP_LOCK = threading.Lock()
_EMOTION_LOCK = threading.Lock()

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_EYE_CORNERS = (33, 133)
RIGHT_EYE_CORNERS = (362, 263)
LEFT_IRIS_CENTER = 468
RIGHT_IRIS_CENTER = 473
NOSE_TIP = 1

EAR_THRESHOLD = 0.21
FACE_CONF_THRESHOLD = 0.6
FACE_AREA_THRESHOLD = 0.045
HEAD_TURN_THRESHOLD = 0.45
GAZE_MIN = 0.18
GAZE_MAX = 0.82
EMOTION_CONF_THRESHOLD = 35.0
BLUR_VARIANCE_THRESHOLD = 45.0
FOCUS_SCORE_THRESHOLD = 0.57
EMOTION_MARGIN_THRESHOLD = 6.0
YAW_ASYMMETRY_THRESHOLD = 0.14
OFF_CENTER_THRESHOLD = 0.18
NON_NEUTRAL_EMOTION_CONF_THRESHOLD = 18.0
NEUTRAL_EMOTION_CONF_THRESHOLD = 28.0
HAPPY_SCORE_BONUS = 4.0


def _env_float(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


EAR_THRESHOLD = _env_float("EAR_THRESHOLD", EAR_THRESHOLD)
FACE_CONF_THRESHOLD = _env_float("FACE_CONF_THRESHOLD", FACE_CONF_THRESHOLD)
FACE_AREA_THRESHOLD = _env_float("FACE_AREA_THRESHOLD", FACE_AREA_THRESHOLD)
HEAD_TURN_THRESHOLD = _env_float("HEAD_TURN_THRESHOLD", HEAD_TURN_THRESHOLD)
GAZE_MIN = _env_float("GAZE_MIN", GAZE_MIN)
GAZE_MAX = _env_float("GAZE_MAX", GAZE_MAX)
EMOTION_CONF_THRESHOLD = _env_float("EMOTION_CONF_THRESHOLD", EMOTION_CONF_THRESHOLD)
BLUR_VARIANCE_THRESHOLD = _env_float("BLUR_VARIANCE_THRESHOLD", BLUR_VARIANCE_THRESHOLD)
FOCUS_SCORE_THRESHOLD = _env_float("FOCUS_SCORE_THRESHOLD", FOCUS_SCORE_THRESHOLD)
EMOTION_MARGIN_THRESHOLD = _env_float("EMOTION_MARGIN_THRESHOLD", EMOTION_MARGIN_THRESHOLD)
YAW_ASYMMETRY_THRESHOLD = _env_float("YAW_ASYMMETRY_THRESHOLD", YAW_ASYMMETRY_THRESHOLD)
OFF_CENTER_THRESHOLD = _env_float("OFF_CENTER_THRESHOLD", OFF_CENTER_THRESHOLD)
NON_NEUTRAL_EMOTION_CONF_THRESHOLD = _env_float(
    "NON_NEUTRAL_EMOTION_CONF_THRESHOLD", NON_NEUTRAL_EMOTION_CONF_THRESHOLD
)
NEUTRAL_EMOTION_CONF_THRESHOLD = _env_float(
    "NEUTRAL_EMOTION_CONF_THRESHOLD", NEUTRAL_EMOTION_CONF_THRESHOLD
)
HAPPY_SCORE_BONUS = _env_float("HAPPY_SCORE_BONUS", HAPPY_SCORE_BONUS)


def _clip01(value):
    return max(0.0, min(1.0, float(value)))


def decode_base64_image(image_data: str):
    try:
        encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def calculate_ear(landmarks, eye_idx):
    p1 = np.array([landmarks[eye_idx[1]].x, landmarks[eye_idx[1]].y])
    p2 = np.array([landmarks[eye_idx[5]].x, landmarks[eye_idx[5]].y])
    p3 = np.array([landmarks[eye_idx[2]].x, landmarks[eye_idx[2]].y])
    p4 = np.array([landmarks[eye_idx[4]].x, landmarks[eye_idx[4]].y])
    p5 = np.array([landmarks[eye_idx[0]].x, landmarks[eye_idx[0]].y])
    p6 = np.array([landmarks[eye_idx[3]].x, landmarks[eye_idx[3]].y])

    vertical_1 = np.linalg.norm(p1 - p2)
    vertical_2 = np.linalg.norm(p3 - p4)
    horizontal = np.linalg.norm(p5 - p6)

    if horizontal <= 1e-6:
        return 0.0
    return float((vertical_1 + vertical_2) / (2.0 * horizontal))


def _eye_gaze_ratio(landmarks, eye_corners, iris_center_idx):
    x0 = landmarks[eye_corners[0]].x
    x1 = landmarks[eye_corners[1]].x
    left = min(x0, x1)
    right = max(x0, x1)
    width = right - left
    if width <= 1e-6:
        return 0.5
    iris_x = landmarks[iris_center_idx].x
    return float((iris_x - left) / width)


def _extract_best_face_bbox(face_detections):
    if not face_detections:
        return None

    best = max(face_detections, key=lambda d: float(d.score[0]) if d.score else 0.0)
    score = float(best.score[0]) if best.score else 0.0
    box = best.location_data.relative_bounding_box
    xmin = max(0.0, float(box.xmin))
    ymin = max(0.0, float(box.ymin))
    xmax = min(1.0, xmin + float(box.width))
    ymax = min(1.0, ymin + float(box.height))

    width = max(0.0, xmax - xmin)
    height = max(0.0, ymax - ymin)
    area = width * height

    return {
        "score": score,
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "area": area,
    }


def _crop_face(img_bgr, bbox, margin=0.15):
    h, w = img_bgr.shape[:2]
    bw = bbox["xmax"] - bbox["xmin"]
    bh = bbox["ymax"] - bbox["ymin"]

    x0 = max(0, int((bbox["xmin"] - margin * bw) * w))
    y0 = max(0, int((bbox["ymin"] - margin * bh) * h))
    x1 = min(w, int((bbox["xmax"] + margin * bw) * w))
    y1 = min(h, int((bbox["ymax"] + margin * bh) * h))

    if x1 <= x0 or y1 <= y0:
        return None
    return img_bgr[y0:y1, x0:x1]


def _prepare_face_for_emotion(face_crop):
    if face_crop is None or face_crop.size == 0:
        return None

    h, w = face_crop.shape[:2]
    if h < 32 or w < 32:
        return None

    ycrcb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    y_eq = clahe.apply(y)
    enhanced = cv2.merge((y_eq, cr, cb))
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_YCrCb2BGR)

    enhanced_resized = cv2.resize(enhanced, (224, 224), interpolation=cv2.INTER_LINEAR)
    raw_resized = cv2.resize(face_crop, (224, 224), interpolation=cv2.INTER_LINEAR)
    return enhanced_resized, raw_resized


def _normalize_emotion_label(label):
    value = str(label).strip().lower()
    if value == "happy":
        return "Happy"
    if value == "sad":
        return "Sad"
    if value == "angry":
        return "Angry"
    if value == "fear":
        return "Fear"
    if value == "disgust":
        return "Disgust"
    if value == "surprise":
        return "Surprise"
    if value == "neutral":
        return "Neutral"
    return value.capitalize() if value else "Neutral"


def _analyze_emotion_scores(face_img, backend):
    with _EMOTION_LOCK:
        analysis = DeepFace.analyze(
            face_img,
            actions=["emotion"],
            enforce_detection=False,
            detector_backend=backend,
            align=True,
            silent=True,
        )

    if isinstance(analysis, list):
        analysis = analysis[0]

    raw = analysis.get("emotion", {})
    return {
        _normalize_emotion_label(key): float(value)
        for key, value in raw.items()
    }


def _predict_emotion(face_crop):
    if face_crop is None or face_crop.size == 0:
        return "Neutral", 0.0, {}

    prepared_faces = _prepare_face_for_emotion(face_crop)
    if prepared_faces is None:
        return "Neutral", 0.0, {}
    enhanced_face, raw_face = prepared_faces

    backends = ["skip", "opencv"]
    primary_scores = None
    secondary_scores = None

    for backend in backends:
        try:
            primary_scores = _analyze_emotion_scores(enhanced_face, backend)
            secondary_scores = _analyze_emotion_scores(raw_face, backend)
            break
        except Exception:
            continue

    if primary_scores is None or secondary_scores is None:
        return "Neutral", 0.0, {}

    all_labels = set(primary_scores) | set(secondary_scores)
    emotion_scores = {
        label: ((0.65 * primary_scores.get(label, 0.0)) + (0.35 * secondary_scores.get(label, 0.0)))
        for label in all_labels
    }

    if not emotion_scores:
        return "Neutral", 0.0, {}

    normalized_scores = dict(emotion_scores)
    best_label = max(normalized_scores, key=normalized_scores.get)
    best_score = float(normalized_scores[best_label])
    ranked = sorted(normalized_scores.items(), key=lambda item: item[1], reverse=True)
    second_best = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second_best

    if best_label == "Neutral":
        if best_score < NEUTRAL_EMOTION_CONF_THRESHOLD or margin < EMOTION_MARGIN_THRESHOLD:
            return "Neutral", best_score, normalized_scores

    if best_label != "Neutral":
        if best_score < NON_NEUTRAL_EMOTION_CONF_THRESHOLD and best_score < (second_best + HAPPY_SCORE_BONUS):
            return "Neutral", best_score, normalized_scores

    return best_label, best_score, normalized_scores


def analyze_frame(img_bgr):
    if img_bgr is None:
        return {
            "emotion": "Neutral",
            "focused": False,
            "metrics": {"reason": "invalid_image"},
        }

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    with _MP_LOCK:
        face_result = _FACE_DETECTION.process(rgb)
        mesh_result = _FACE_MESH.process(rgb)

    bbox = _extract_best_face_bbox(face_result.detections if face_result else None)
    has_face = bbox is not None
    face_score = bbox["score"] if bbox else 0.0
    face_area = bbox["area"] if bbox else 0.0

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    face_center_offset = 0.0
    if bbox:
        face_center_x = (bbox["xmin"] + bbox["xmax"]) / 2.0
        face_center_offset = abs(face_center_x - 0.5)

    metrics = {
        "face_detected": has_face,
        "face_confidence": round(face_score, 3),
        "face_area": round(face_area, 3),
        "face_center_offset": round(face_center_offset, 3),
        "ear": None,
        "head_turn_ratio": None,
        "yaw_asymmetry": None,
        "gaze_ratio": None,
        "blur_variance": round(blur_variance, 2),
        "focus_score": 0.0,
        "reason": "ok",
    }

    focused = True
    reason = "ok"

    if not has_face:
        focused = False
        reason = "no_face"
    elif face_score < FACE_CONF_THRESHOLD:
        focused = False
        reason = "low_face_confidence"
    elif face_area < FACE_AREA_THRESHOLD:
        focused = False
        reason = "face_too_small"

    if focused:
        if not mesh_result or not mesh_result.multi_face_landmarks:
            focused = False
            reason = "no_landmarks"
        else:
            lm = mesh_result.multi_face_landmarks[0].landmark

            left_ear = calculate_ear(lm, LEFT_EYE)
            right_ear = calculate_ear(lm, RIGHT_EYE)
            avg_ear = (left_ear + right_ear) / 2.0

            left_eye_x = lm[LEFT_EYE_CORNERS[0]].x
            right_eye_x = lm[RIGHT_EYE_CORNERS[1]].x
            eye_distance = abs(right_eye_x - left_eye_x)
            nose_x = lm[NOSE_TIP].x
            eye_mid_x = (left_eye_x + right_eye_x) / 2.0
            head_turn_ratio = abs(nose_x - eye_mid_x) / (eye_distance + 1e-6)

            left_dist = abs(nose_x - left_eye_x)
            right_dist = abs(right_eye_x - nose_x)
            yaw_asymmetry = abs(left_dist - right_dist) / (left_dist + right_dist + 1e-6)

            left_gaze = _eye_gaze_ratio(lm, LEFT_EYE_CORNERS, LEFT_IRIS_CENTER)
            right_gaze = _eye_gaze_ratio(lm, RIGHT_EYE_CORNERS, RIGHT_IRIS_CENTER)
            gaze_ratio = (left_gaze + right_gaze) / 2.0

            metrics["ear"] = round(avg_ear, 3)
            metrics["head_turn_ratio"] = round(head_turn_ratio, 3)
            metrics["yaw_asymmetry"] = round(yaw_asymmetry, 3)
            metrics["gaze_ratio"] = round(gaze_ratio, 3)

            gaze_center = (GAZE_MIN + GAZE_MAX) / 2.0
            gaze_half = max(1e-6, (GAZE_MAX - GAZE_MIN) / 2.0)

            ear_score = _clip01(avg_ear / max(EAR_THRESHOLD, 1e-6))
            head_score = _clip01(1.0 - (head_turn_ratio / max(HEAD_TURN_THRESHOLD, 1e-6)))
            yaw_score = _clip01(1.0 - (yaw_asymmetry / max(YAW_ASYMMETRY_THRESHOLD, 1e-6)))
            gaze_dev = abs(gaze_ratio - gaze_center) / gaze_half
            gaze_score = _clip01(1.0 - gaze_dev)
            blur_score = _clip01(blur_variance / max(BLUR_VARIANCE_THRESHOLD, 1e-6))
            center_score = _clip01(1.0 - (face_center_offset / max(OFF_CENTER_THRESHOLD, 1e-6)))

            focus_score = (
                0.22 * ear_score
                + 0.20 * head_score
                + 0.18 * yaw_score
                + 0.20 * gaze_score
                + 0.10 * center_score
                + 0.15 * blur_score
            )
            metrics["focus_score"] = round(focus_score, 3)

            if avg_ear < (EAR_THRESHOLD * 0.85):
                focused = False
                reason = "eyes_closed"
            elif blur_variance < (BLUR_VARIANCE_THRESHOLD * 0.35):
                focused = False
                reason = "frame_too_blurry"
            elif face_center_offset > OFF_CENTER_THRESHOLD:
                focused = False
                reason = "face_off_center"
            elif yaw_asymmetry > YAW_ASYMMETRY_THRESHOLD:
                focused = False
                reason = "head_turned"
            elif focus_score < FOCUS_SCORE_THRESHOLD:
                focused = False
                if head_turn_ratio > HEAD_TURN_THRESHOLD or yaw_asymmetry > YAW_ASYMMETRY_THRESHOLD:
                    reason = "head_turned"
                elif gaze_ratio < GAZE_MIN or gaze_ratio > GAZE_MAX:
                    reason = "looking_away"
                elif face_center_offset > OFF_CENTER_THRESHOLD:
                    reason = "face_off_center"
                else:
                    reason = "low_focus_score"

    if not focused and metrics["focus_score"] == 0.0:
        metrics["focus_score"] = round(
            0.5 * _clip01(face_score) + 0.5 * _clip01(face_area / max(FACE_AREA_THRESHOLD, 1e-6)),
            3,
        )

    metrics["reason"] = reason

    face_crop = _crop_face(img_bgr, bbox) if has_face else None
    emotion, emotion_score, emotion_scores = _predict_emotion(face_crop)
    metrics["emotion_confidence"] = round(float(emotion_score), 2)
    metrics["emotion_scores"] = {
        key: round(float(value), 2) for key, value in emotion_scores.items()
    }

    if not has_face:
        emotion = "Neutral"

    return {"emotion": emotion, "focused": focused, "metrics": metrics}


class DetectionSmoother:
    def __init__(self, window_size=7):
        self.emotion_history = deque(maxlen=window_size)
        self.focus_history = deque(maxlen=window_size)

    def update(self, emotion, focused):
        self.emotion_history.append(emotion)
        self.focus_history.append(bool(focused))

        emotion_mode = "Neutral"
        if self.emotion_history:
            weighted_votes = Counter()
            history = list(self.emotion_history)
            for idx, label in enumerate(history, start=1):
                weighted_votes[label] += idx
            emotion_mode = weighted_votes.most_common(1)[0][0]

        focused_votes = sum(1 for val in self.focus_history if val)
        smoothed_focus = focused_votes >= (len(self.focus_history) / 2.0)
        return emotion_mode, smoothed_focus


__all__ = ["DetectionSmoother", "analyze_frame", "decode_base64_image"]