# FocusSpark Backend

FastAPI-based AI study assistant backend with real-time focus/emotion detection, intelligent content generation, and progress tracking.

## Features

- **Authentication**: JWT-based user authentication with secure password hashing
- **AI Chat**: Real-time chat with AI tutor for personalized explanations
- **Document Chat**: Upload PDF, DOCX, PPTX, or TXT files and ask the AI to explain them
- **Flashcards**: AI-generated flashcards from topics or chat conversations
- **Quizzes**: Adaptive quizzes with multiple difficulty levels
- **Focus Detection**: Real-time emotion and focus state analysis via WebSocket
- **Study Tracking**: Session logging, distraction events, and achievement system

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLModel (SQLAlchemy ORM)
- **Auth**: JWT (python-jose) + Bcrypt hashing
- **AI**: OpenAI API / GitHub Models
- **Vision**: OpenCV + MediaPipe + DeepFace
- **Server**: Uvicorn

## Setup

### Environment Variables

Create `.env` in project root:

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@127.0.0.1:5432/focusspark
JWT_SECRET=your-32-character-secret-key-here
AI_PROVIDER=openai
GITHUB_MODEL=gpt-4.1
GITHUB_TOKEN=github_pat_xxxxx
GITHUB_MODELS_ENDPOINT=https://models.inference.ai.azure.com
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=1000
```

### Installation

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

The main venv is intended for PostgreSQL. `requirements.txt` already includes the runtime packages used by the app, including `psycopg2-binary` for Postgres and `openai` for the AI provider.

### Running the Server

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Access:**
- API: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Authentication

**Protected Routes** require `Authorization: Bearer <token>` header.

**Public Routes:**
- `GET /` - Health check
- `POST /auth/signup` - Create account
- `POST /auth/login` - Get token
- `POST /analyze` - Focus analysis (single frame)
- `WS /ws` - Focus detection (streaming)

---

## API Endpoints

### Authentication

#### 1. **Sign Up**
```
POST /auth/signup
```
**Request:**
```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!",
  "academic_focus": "Computer Science",
  "accepted_terms": true
}
```
**Academic Focus Options:** Computer Science, Medicine, Engineering, Business, Law, Psychology, Biology, Mathematics, Physics, Other

**Response (200):**
```json
{
  "id": 1,
  "email": "john@example.com",
  "full_name": "John Doe"
}
```

#### 2. **Login**
```
POST /auth/login
```
**Request:**
```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```
**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### 3. **Get Profile**
```
GET /auth/profile
Authorization: Bearer <token>
```
**Response (200):**
```json
{
  "id": 1,
  "email": "john@example.com",
  "full_name": "John Doe",
  "academic_focus": "Computer Science",
  "created_at": "2026-05-10T14:30:00"
}
```

#### 4. **Delete Account**
```
DELETE /auth/delete-user
Authorization: Bearer <token>
```
```

---

**Recent Backend Changes (2026-05-19)**

- Added study history endpoint: `GET /study/sessions/history?start_date=&end_date=` returning raw `StudySession` rows for frontend graphs and heatmaps.
- Added export endpoint: `GET /study/export?format=json|csv` — JSON returns sessions, achievements, settings; CSV returns session rows as an attachment.
- Achievements expanded: achievements now include criteria metadata and the API returns computed `progress_current`/`progress_target` plus `unlocked`/`unlocked_at` for each user so the frontend can render progress bars without re-computing everything client-side.
- User settings expanded with common frontend preferences (pomodoro durations, AI persona, focus sensitivity, fallback method, integrations, appearance, accessibility, privacy). Use `GET /study/settings` and `PUT /study/settings`.
- Seeded a small set of default achievements on DB init to populate the frontend immediately.

Notes on migrations:
- If you already have a running database, `SQLModel.metadata.create_all(engine)` will not alter existing columns to add new fields. Please create and run a migration (Alembic or your preferred tool) to add the new columns to `achievements`, `user_achievements`, and `user_settings` tables before deploying.

Frontend wiring:
- The frontend currently uses local/mock data for achievements, reports and settings in several screens. To switch to the real backend, update the frontend to call the following routes and adapt field names as shown in `temp.md`:
  - `/study/achievements` (returns progress_current/progress_target, unlocked, unlocked_at)
  - `/study/sessions/history` (returns sessions by date range)
  - `/study/export` (download JSON/CSV)
  - `/study/settings` (get / put user preferences)

If you want, I can next patch the frontend to consume these endpoints and map the fields to the UI components.
**Response (200):**
```json
{
  "message": "User deleted successfully"
}
```

---

### Chat (AI Tutor)

#### 1. **Get Chat Threads**
```
GET /chat/threads
Authorization: Bearer <token>
```
**Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "title": "Operating Systems Help",
    "created_at": "2026-05-10T14:30:00"
  }
]
```

#### 2. **Create Chat Thread**
```
POST /chat/threads
Authorization: Bearer <token>
```
**Request:**
```json
{
  "title": "Data Structures Questions",
  "ai_provider": "openai"
}
```
**Response (201):**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "Data Structures Questions",
  "ai_provider": "openai",
  "ai_model": "gpt-4.1",
  "created_at": "2026-05-10T14:30:00"
}
```

#### 3. **Send Chat Message**
```
POST /chat/
Authorization: Bearer <token>
```
**Request:**
```json
{
  "message": "Explain what a binary search tree is",
  "thread_id": 1
}
```
**Response (200):**
```json
{
  "response": "A binary search tree (BST) is a tree data structure where each node has at most two children...",
  "message_id": 42
}
```

#### 4. **Get Message Artifacts**
```
GET /chat/message/{message_id}/artifacts
Authorization: Bearer <token>
```
**Response (200):**
```json
[
  {
    "id": 1,
    "message_id": 42,
    "artifact_type": "flashcard_deck",
    "artifact_id": 5
  }
]
```

#### 5. **Explain an Uploaded Document**
```
POST /chat/document
Authorization: Bearer <token>
Content-Type: multipart/form-data
```
**Form Data:**
```text
thread_id=1
message=Explain the main idea of this document
file=<PDF, DOCX, PPTX, or TXT file>
```
**Supported formats:** PDF, DOCX, PPTX, TXT

**Behavior:** The backend extracts the text in memory, sends it to the AI, and does not save the uploaded file in the database.

**Response (200):**
```json
{
  "response": "This document explains...",
  "message_id": 43
}
```

---

### Flashcards

#### 1. **Get All Decks**
```
GET /flashcards/
Authorization: Bearer <token>
```
**Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "title": "Binary Trees Flashcards",
    "topic": "Binary Trees",
    "total_cards": 12,
    "created_at": "2026-05-10T14:30:00"
  }
]
```

#### 2. **Get Flashcards in Deck**
```
GET /flashcards/{deck_id}
Authorization: Bearer <token>
```
**Response (200):**
```json
[
  {
    "id": 1,
    "deck_id": 1,
    "front": "What is a binary tree?",
    "back": "A tree where each node has at most 2 children (left and right)",
    "position": 1
  }
]
```

#### 3. **Generate from Topic**
```
POST /flashcards/generate
Authorization: Bearer <token>
```
**Request:**
```json
{
  "topic": "Binary Search Trees"
}
```
**Response (200):**
```json
{
  "deck": {
    "id": 5,
    "user_id": 1,
    "title": "Binary Search Trees Flashcards",
    "topic": "Binary Search Trees",
    "total_cards": 10,
    "created_at": "2026-05-10T14:35:00"
  },
  "flashcards": [
    {
      "id": 1,
      "deck_id": 5,
      "front": "Define BST",
      "back": "A binary tree where left < parent < right",
      "position": 1
    }
  ]
}
```

#### 4. **Generate from Chat**
```
POST /flashcards/from-chat
Authorization: Bearer <token>
```
**Request:**
```json
{
  "message_id": 42
}
```
**Response (200):** Same as Generate from Topic

---

### Quizzes

#### 1. **Get All Quizzes**
```
GET /quiz/
Authorization: Bearer <token>
```
**Response (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "title": "OS Basics Quiz",
    "topic": "Operating Systems",
    "difficulty": "Beginner",
    "created_at": "2026-05-10T14:30:00"
  }
]
```

#### 2. **Get Quiz Questions**
```
GET /quiz/{quiz_id}
Authorization: Bearer <token>
```
**Response (200):**
```json
[
  {
    "id": 1,
    "quiz_id": 1,
    "question": "What is a process?",
    "options": ["A file", "A running program", "Memory block", "CPU instruction"],
    "correct_answer_index": 1
  }
]
```

#### 3. **Generate from Topic**
```
POST /quiz/generate
Authorization: Bearer <token>
```
**Request:**
```json
{
  "topic": "Database Design",
  "difficulty": "Intermediate"
}
```
**Difficulty Options:** Beginner, Intermediate, Advanced

**Response (200):**
```json
{
  "quiz": {
    "id": 3,
    "user_id": 1,
    "title": "Database Design Quiz",
    "topic": "Database Design",
    "difficulty": "Intermediate",
    "created_at": "2026-05-10T14:40:00"
  },
  "questions": [
    {
      "id": 1,
      "quiz_id": 3,
      "question": "What is normalization?",
      "options": ["Organizing data", "Removing duplicates", "Organizing data to reduce redundancy", "All above"],
      "correct_answer_index": 2
    }
  ]
}
```

#### 4. **Generate from Chat**
```
POST /quiz/from-chat
Authorization: Bearer <token>
```
**Request:**
```json
{
  "message_id": 42
}
```
**Response (200):** Same format as Generate from Topic

---

### Focus & Emotion Detection

#### 1. **Single Frame Analysis**
```
POST /analyze
```
**Request:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
}
```
**Response (200):**
```json
{
  "emotion": "Neutral",
  "focused": true,
  "metrics": {
    "reason": "ok"
  }
}
```

#### 2. **Real-time WebSocket Stream**
```
WS /ws
```
**Client sends (text frames):**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
}
```
**Server responds:**
```json
{
  "emotion": "Happy",
  "focused": true,
  "metrics": {
    "reason": "ok"
  }
}
```

**Supported Emotions:** Angry, Disgust, Fear, Happy, Neutral, Sad, Surprise

---

## Database

Tables auto-created on startup:
- **users** - User accounts
- **chat_threads, chat_messages** - Chat history
- **flashcard_decks, flashcards** - Study materials
- **quiz_questions, quiz_attempts** - Assessments
- **study_sessions, emotion_logs** - Progress tracking
- **achievements, notifications** - Gamification

See [DB.txt](DB.txt) for schema details.

---

## Error Handling

Standard HTTP status codes:
- **200** - Success
- **400** - Bad request (validation error)
- **401** - Unauthorized
- **403** - Forbidden
- **404** - Not found
- **500** - Server error
- **502** - AI provider error

---

## Development Notes

- No trailing slash on routes
- All timestamps in ISO 8601 format
- CORS enabled for all origins in development
- Database auto-migrates on startup

### Chat

- GET /chat/threads
- POST /chat/threads
- GET /chat/threads/{thread_id}
- POST /chat/
- GET /chat/message/{message_id}/artifacts

Create thread body:

```json
{
	"title": "My Study Thread"
}
```

Chat message body:

```json
{
	"message": "Explain operating systems in simple terms",
	"thread_id": 1
}
```

Chat response:

```json
{
	"response": "...AI reply...",
	"message_id": 42
}
```

Artifacts endpoint returns records linked to a message (for example deck/quiz artifacts).

### Flashcards

- GET /flashcards/
- GET /flashcards/{deck_id}
- POST /flashcards/generate
- POST /flashcards/from-chat

Generate from topic body:

```json
{
	"topic": "Operating Systems"
}
```

Generate from chat body:

```json
{
	"message_id": 42
}
```

Generate response shape:

```json
{
	"deck": {
		"id": 5,
		"user_id": 1,
		"title": "Operating Systems Flashcards",
		"description": null,
		"topic": "Operating Systems",
		"source": "ai",
		"created_from_message_id": null,
		"created_at": "2026-05-10T12:10:00",
		"updated_at": "2026-05-10T12:10:00"
	},
	"flashcards": [
		{
			"id": 1,
			"front": "What is a process?",
			"back": "A running instance of a program"
		}
	]
}
```

### Quiz

- GET /quiz/
- GET /quiz/{quiz_id}
- POST /quiz/generate
- POST /quiz/from-chat

Generate from topic body:

```json
{
	"topic": "Operating Systems",
	"difficulty": "Beginner"
}
```

Allowed difficulty values:

- Beginner
- Intermediate
- Advanced

Generate from chat body:

```json
{
	"message_id": 42
}
```

Generate response shape:

```json
{
	"quiz": {
		"id": 3,
		"user_id": 1,
		"title": "Operating Systems Quiz",
		"description": null,
		"difficulty": "Beginner",
		"topic": "Operating Systems",
		"source": "ai",
		"created_from_message_id": null,
		"created_at": "2026-05-10T12:10:00"
	},
	"questions": [
		{
			"id": 1,
			"quiz_id": 3,
			"question": "Which scheduler picks the next process?",
			"options": ["Long-term", "Short-term", "Medium-term", "None"],
			"correct_answer_index": 1,
			"explanation": null
		}
	]
}
```

Note: when reading quiz questions from GET /quiz/{quiz_id}, options are stored as a JSON string in the database model.

### Focus + Emotion

- POST /analyze
- WS /ws

Analyze body:

```json
{
	"image": "data:image/jpeg;base64,/9j/4AAQSk..."
}
```

Analyze response:

```json
{
	"emotion": "Neutral",
	"focused": true,
	"metrics": {
		"reason": "ok"
	}
}
```

WebSocket expectations:

- Client sends JSON text frames like: {"image": "<base64-image>"}
- Server responds with: emotion, focused, metrics
- If payload is invalid, server returns error JSON (for example image_required or invalid_json)

## Database Startup Behavior

On startup:

- SQLModel metadata is created automatically.

## Database Status

The file [DB.txt](DB.txt) is the target database design for the FYP. The codebase is aligned with the main product flow, but the database is not fully at the final target schema yet.

Current implemented tables in the backend include:

- users
- chat_threads
- chat_messages
- message_artifacts
- documents
- flashcard_decks
- flashcards
- flashcard_reviews
- quizzes
- quiz_questions
- quiz_attempts
- quiz_attempt_answers
- study_sessions
- distraction_events
- emotion_logs
- study_goals
- achievements
- user_achievements
- notifications
- user_settings

Current implementation notes:

- IDs are integer-based in the current SQLModel models, while the target design in [DB.txt](DB.txt) uses UUIDs.
- Some app-specific auth fields are still present in the backend, including academic_focus and accepted_terms.
- The backend currently supports the core features needed for the app flow: auth, chat, flashcards, quizzes, and focus/emotion detection.
- The schema is now much closer to [DB.txt](DB.txt), but a full UUID migration would still be needed to make it identical.

## Current Route Summary

Included routers:

- auth_router
- flashcard_router
- quiz_router
- chat_router
- focus_router
- study_router

### Added Workflow Routes

These route groups are now exposed in the API surface:

- study goals: `/study/goals`
- achievements: `/study/achievements` and `/study/achievements/unlocked`
- notifications: `/study/notifications`
- user settings: `/study/settings`
- flashcard reviews: `/flashcards/reviews` and `/flashcards/{flashcard_id}/review`
- quiz attempts: `/quiz/{quiz_id}/attempts`

### Remaining Gaps

The core route set is now covered. If you want fuller product coverage, the main remaining gaps are:

- full CRUD for chat threads, flashcard decks, and quizzes
- document upload and document management endpoints
- automated achievement awarding rules
- richer account/profile update endpoints
