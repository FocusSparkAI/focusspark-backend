from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import CORS_ORIGINS
from app.core.logging import configure_logging
from app.db.database import init_db
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import auth_router, flashcard_router, quiz_router, chat_router, focus_router, study_router

configure_logging()

Path("uploads").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="FocusSpark API")

app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(auth_router.router)
app.include_router(flashcard_router.router)
app.include_router(quiz_router.router)
app.include_router(chat_router.router)
app.include_router(focus_router.router)
app.include_router(study_router.router)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
def root():
    return {"message": "FocusSpark Backend Running"}
