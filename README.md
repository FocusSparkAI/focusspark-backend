# FocusSpark Backend

FocusSpark Backend is the FastAPI service for the FocusSpark study platform. It handles authentication, profiles, AI study tools, focus analysis, study tracking, achievements, notifications, settings, analytics, and exports.

## Tech Stack

- FastAPI
- SQLModel / SQLAlchemy
- PostgreSQL
- JWT auth with `python-jose`
- Bcrypt password hashing
- OpenAI / GitHub Models provider support
- Gemini provider support
- OpenCV, MediaPipe, and DeepFace for focus/emotion analysis
- Request logging middleware with optional rotating file logs
- Docker and Docker Compose for local container testing
- Uvicorn

## Features

- JWT signup/login with secure password hashing
- Profile API with bio, avatar URL, avatar upload/delete, academic focus, password changes, and last-login tracking
- AI chat threads, regular chat, document chat, and generated artifacts
- AI flashcard and quiz generation from topics or chat messages
- Flashcard review tracking
- Quiz attempts, scoring, and attempt history
- Single-frame and WebSocket focus/emotion detection
- Study sessions, goals, analytics, dashboard stats, and reports data
- Achievements, user progress, manual unlock support, and achievement notifications
- Notifications and mark-read APIs
- User settings for theme, Pomodoro durations, AI model preferences, focus preferences, extension notifications, and accessibility extras
- Backend JSON/CSV study data export
- Account data clearing

## Environment

Create `.env` in the backend project root for normal local development:

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@127.0.0.1:5432/focusspark
JWT_SECRET=your-32-character-secret-key-here
AI_PROVIDER=openai
GITHUB_MODEL=gpt-4.1
GITHUB_TOKEN=github_pat_xxxxx
GITHUB_MODELS_ENDPOINT=https://models.inference.ai.azure.com
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=1000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE=logs/app.log
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=5
SQL_ECHO=false
```

Gemini can be used instead of the OpenAI-compatible GitHub Models provider:

```env
AI_PROVIDER=gemini
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL=gemini-2.5-flash
```

## Install and Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Access:

- API: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Docker

The `Dockerfile` builds the FastAPI backend image and runs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Build and run only the backend image:

```bash
docker build -t focusspark-backend .
docker run --env-file .env -p 8000:8000 focusspark-backend
```

If PostgreSQL is running directly on your Windows host machine, use `host.docker.internal` in the container database URL:

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@host.docker.internal:5432/focusspark
```

## Docker Compose Local Testing

`docker-compose.yaml` is for local testing with three services:

- `backend`: this FastAPI app
- `db`: local PostgreSQL container
- `adminer`: database UI

`.env.docker` is the environment file used by the backend container when running with Compose. It is ignored by git because it can contain secrets. Use `.env.docker.example` as the template.

Create `.env.docker`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:pwd@db:5432/focusspark
JWT_SECRET=your-local-secret-key
```

Run locally:

```bash
docker compose up --build
```

Stop containers:

```bash
docker compose down
```

Remove containers and the local database volume:

```bash
docker compose down -v
```

Local URLs:

- Backend: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Adminer: `http://localhost:5555`

Adminer login:

```text
System: PostgreSQL
Server: db
Username: postgres
Password: pwd
Database: focusspark
```

When switching to Neon, keep the Compose file for local testing and change only `DATABASE_URL` in the environment used by the backend:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/neondb?sslmode=require
```

## Authentication

Protected routes require:

```http
Authorization: Bearer <token>
```

### Sign Up

```http
POST /auth/signup
```

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

Academic focus values:

- Computer Science
- Medicine
- Engineering
- Business
- Law
- Psychology
- Biology
- Mathematics
- Physics
- Other

### Login

```http
POST /auth/login
```

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

Successful login updates `users.last_login` and returns an access token.

### Profile

```http
GET /auth/profile
```

Example response:

```json
{
  "id": 1,
  "full_name": "John Doe",
  "email": "john@example.com",
  "academic_focus": "Computer Science",
  "bio": null,
  "avatar_url": null,
  "last_login": "2026-05-25T04:30:00",
  "created_at": "2026-05-10T14:30:00"
}
```

Auth/profile routes:

- `POST /auth/signup`
- `POST /auth/login`
- `PATCH /auth/password`
- `GET /auth/profile`
- `PATCH /auth/profile`
- `POST /auth/profile/avatar`
- `DELETE /auth/profile/avatar`
- `DELETE /auth/delete-user`

Avatar uploads accept image files, validate content, resize/crop to a square image, save under `uploads/avatars`, and serve files through `/uploads`.

## Study Routes

Sessions:

- `POST /study/sessions`
- `PATCH /study/sessions/{session_id}/complete`
- `POST /study/sessions/{session_id}/distractions`
- `POST /study/sessions/{session_id}/emotions`
- `GET /study/sessions/recent`
- `GET /study/sessions/history`

Stats:

- `GET /study/stats/summary`
- `GET /study/stats/analytics`
- `GET /study/stats/dashboard`

Goals:

- `POST /study/goals`
- `GET /study/goals`
- `GET /study/goals/{goal_id}`
- `PATCH /study/goals/{goal_id}`
- `DELETE /study/goals/{goal_id}`

Achievements:

- `GET /study/achievements`
- `GET /study/achievements/unlocked`
- `POST /study/achievements/{achievement_id}/unlock`

Notifications:

- `GET /study/notifications`
- `PATCH /study/notifications/read-all`
- `PATCH /study/notifications/{notification_id}`

Settings and exports:

- `GET /study/settings`
- `PUT /study/settings`
- `GET /study/export?format=json`
- `GET /study/export?format=csv`
- `DELETE /study/data`

`GET /study/export` also supports optional `start_date` and `end_date` filters.

## User Settings

```http
GET /study/settings
PUT /study/settings
```

Settings include:

- `dark_mode`
- `pomodoro_duration_minutes`
- `break_duration_minutes`
- `ai_persona`
- `preferred_ai_provider`
- `preferred_ai_model`
- `focus_sensitivity`
- `fallback_method`
- `notifications_enabled`
- `focus_alerts_enabled`
- `integrations`
- `appearance`
- `accessibility`
- `privacy`

The web settings page uses `notifications_enabled` as the "Extension Notifications" preference. The extension bell dropdown reads this setting and shows "Notifications off" when it is disabled.

## AI Study Routes

Chat:

- `GET /chat/threads`
- `POST /chat/threads`
- `GET /chat/threads/{thread_id}`
- `POST /chat/`
- `POST /chat/document`
- `GET /chat/message/{message_id}/artifacts`

Flashcards:

- `GET /flashcards/`
- `GET /flashcards/reviews`
- `GET /flashcards/{deck_id}`
- `POST /flashcards/generate`
- `POST /flashcards/from-chat`
- `PUT /flashcards/{flashcard_id}/review`

Quizzes:

- `GET /quiz/`
- `GET /quiz/{quiz_id}`
- `GET /quiz/{quiz_id}/questions`
- `GET /quiz/{quiz_id}/items`
- `POST /quiz/generate`
- `POST /quiz/from-chat`
- `GET /quiz/{quiz_id}/attempts`
- `POST /quiz/{quiz_id}/attempts`

## Focus Analysis

Single frame:

```http
POST /analyze
```

WebSocket stream:

```http
WS /ws?token=<access_token>
```

Expected payload:

```json
{
  "image": "data:image/jpeg;base64,..."
}
```

Response includes:

- `emotion`
- `focused`
- `metrics`

## Database

Current implemented tables include:

- users
- expired_tokens
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

`init_db()` creates missing tables, seeds default achievements, and adds selected compatibility columns for existing tables.

## Development Notes

- No trailing slash is required on routes.
- Timestamps are returned in ISO 8601 format.
- CORS is open for development and can be configured with `CORS_ORIGINS`.
- Request logs are written through `RequestLoggingMiddleware`; file logging writes to `logs/app.log` by default.
- Uploaded profile/avatar files are served from `/uploads`.
- Achievement defaults are seeded on DB init.
- IDs are integer-based in the current SQLModel implementation.
- `.env`, `.env.*`, logs, uploads, virtual environments, and cache folders are ignored by git.
- `.dockerignore` keeps secrets and local-only files out of Docker build context.
- The backend is aligned with the current web frontend and extension flow, while a future UUID schema update may still be needed if you want the schema to match a UUID-first final design.
