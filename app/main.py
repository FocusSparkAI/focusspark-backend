from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import init_db
from app.routers import auth_router, flashcard_router, quiz_router, chat_router, focus_router, study_router

app = FastAPI(title="FocusSpark API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/")
def root():
    return {"message": "FocusSpark Backend Running"}