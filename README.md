# FocusSpark Backend

FastAPI backend for FocusSpark, an AI-assisted study platform for focus tracking, Pomodoro study sessions, analytics, achievements, quizzes, flashcards, document chat, and user profiles.

This service powers both the web frontend and the Chrome extension.

For the complete multi-project setup, start with the root `README.md`.

## Tech Stack

- FastAPI and Uvicorn
- SQLModel / SQLAlchemy
- PostgreSQL
- JWT authentication with `python-jose`
- Password hashing with Bcrypt / Passlib
- OpenAI-compatible GitHub Models provider
- Gemini provider
- OpenCV, MediaPipe, Pillow, and DeepFace for focus/emotion and image handling
- Cloudinary for hosted profile pictures
- Docker and Docker Compose for local container testing

## Features

- Signup, login, JWT protected routes, password changes, and account deletion
- Profile management with name, academic focus, bio, timezone, last login, and profile picture upload/delete
- Cloudinary-backed avatar storage with image validation, crop/resize processing, overwrite support, and old-avatar cleanup
- AI chat threads, document chat, and generated artifacts
- AI-generated flashcards and quizzes from topics or chat messages
- Quiz attempts, scoring, history, and answer tracking
- Flashcard review tracking
- Single-frame and WebSocket focus/emotion analysis
- Study sessions, distractions, emotion logs, goals, dashboard stats, analytics, and reports data
- Achievements, user progress, manual unlock support, and achievement notifications
- Notifications and read-state APIs
- User settings for theme, Pomodoro timings, AI preferences, focus preferences, extension notifications, accessibility, privacy, and appearance
- JSON/CSV export and account data clearing

## Environment

Create `.env` in `FocusSpark-Backend/`.

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@127.0.0.1:5432/focusspark
JWT_SECRET=your-32-character-secret-key-here

AI_PROVIDER=openai
GITHUB_MODEL=gpt-4.1
GITHUB_TOKEN=github_pat_xxxxx
GITHUB_MODELS_ENDPOINT=https://models.inference.ai.azure.com
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=1000

CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE=logs/app.log
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=5
SQL_ECHO=false

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-email-password
SMTP_FROM_EMAIL=no-reply@focusspark.local
SMTP_FROM_NAME=FocusSpark
SMTP_USE_TLS=true
EMAIL_LOGO_URL=https://example.com/logo.png
EMAIL_VERIFICATION_OTP_MINUTES=10
PASSWORD_RESET_OTP_MINUTES=10
```

To use Gemini instead of the OpenAI-compatible provider:

```env
AI_PROVIDER=gemini
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL=gemini-2.5-flash
```

## Install and Run

From this folder:

```bash
cd FocusSpark-Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Before running locally without Docker, make sure PostgreSQL is running and the database in `DATABASE_URL` exists. With the sample value above, create a local database named `focusspark`.

Local URLs:

- API: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Health check:

- `GET /` returns `{"message": "FocusSpark Backend Running"}`

## Docker

Build and run the backend image:

```bash
docker build -t focusspark-backend .
docker run --env-file .env -p 8000:8000 focusspark-backend
```

If PostgreSQL is running on the Windows host, use `host.docker.internal`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@host.docker.internal:5432/focusspark
```

## Docker Compose

`docker-compose.yaml` runs:

- `backend`: FastAPI app
- `db`: PostgreSQL
- `adminer`: database UI

Create `.env.docker`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:pwd@db:5432/focusspark
JWT_SECRET=your-32-character-secret-key-here
AI_PROVIDER=openai
GITHUB_TOKEN=github_pat_xxxxx
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173
```

Run:

```bash
cd FocusSpark-Backend
docker compose up --build
```

Stop:

```bash
docker compose down
```

Stop and remove the local database volume:

```bash
docker compose down -v
```

Local Compose URLs:

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

For Neon or another hosted PostgreSQL database, keep the Compose file for local testing and update only `DATABASE_URL`:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/neondb?sslmode=require
```

## Authentication

Protected routes require:

```http
Authorization: Bearer <token>
```

Main auth/profile routes:

- `POST /auth/signup`
- `POST /auth/verify-email`
- `POST /auth/resend-verification-otp`
- `POST /auth/login`
- `POST /auth/forgot-password`
- `POST /auth/verify-password-reset-otp`
- `POST /auth/reset-password`
- `PATCH /auth/password`
- `GET /auth/profile`
- `PATCH /auth/profile`
- `POST /auth/profile/avatar`
- `DELETE /auth/profile/avatar`
- `DELETE /auth/delete-user`

Email verification and password-reset routes use short-lived OTP codes. If `SMTP_HOST` is not configured, the email service logs the message instead of sending it.

Signup example:

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

Login example:

```http
POST /auth/login
```

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

Profile example:

```http
GET /auth/profile
```

```json
{
  "id": 1,
  "full_name": "John Doe",
  "email": "john@example.com",
  "academic_focus": "Computer Science",
  "bio": null,
  "avatar_url": "https://res.cloudinary.com/example/image/upload/...",
  "timezone": "Asia/Karachi",
  "last_login": "2026-05-25T04:30:00",
  "created_at": "2026-05-10T14:30:00"
}
```

## Profile Pictures

`POST /auth/profile/avatar` accepts an authenticated multipart image upload.

Validation and processing:

- Accepts image content types only
- Rejects empty files
- Rejects files larger than 2 MB
- Allows `.jpg`, `.jpeg`, `.png`, `.gif`, and `.webp`
- Limits source dimensions to 1024 px
- Center-crops to square and resizes to 256 x 256
- Uploads to Cloudinary under `focusspark/avatars`
- Uses `user-{user_id}` as the public ID and overwrites the previous image
- Stores `avatar_url` and `avatar_public_id` on the user

`DELETE /auth/profile/avatar` removes the Cloudinary asset when possible and clears the database fields. The backend also keeps compatibility cleanup for old local `/uploads/avatars` profile images.

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

`GET /study/export` supports optional `start_date` and `end_date` filters.

Example:

```http
GET /study/export?format=json&start_date=2026-04-15&end_date=2026-06-01
```

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
- `PUT /flashcards/{deck_id}/review-complete`

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

Single-frame analysis:

```http
POST /analyze
```

WebSocket stream:

```http
WS /ws?token=<access_token>
```

Expected image payload:

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

`init_db()` creates missing tables, seeds default achievements, and adds selected compatibility columns for existing tables, including profile/avatar-related columns.

## Useful Commands

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
python -m compileall app
```

## Development Notes

- No trailing slash is required on routes.
- Timestamps are returned in ISO 8601 format.
- CORS is open for development and can be configured with `CORS_ORIGINS`.
- Request logs are written through `RequestLoggingMiddleware`.
- Cloudinary is required for new profile-picture uploads.
- Old local profile-picture paths are still cleaned up during avatar replacement/removal.
- Achievement defaults are seeded on database initialization.
- IDs are integer-based in the current SQLModel implementation.
- `.env`, `.env.*`, logs, uploads, virtual environments, and cache folders should stay out of git.
