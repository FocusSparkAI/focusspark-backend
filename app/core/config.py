import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is not set")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default

    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


CORS_ORIGINS = _csv_env(
    "CORS_ORIGINS",
    [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").strip().lower() in {"1", "true", "yes", "on"}
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "5242880"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
SQL_ECHO = os.getenv("SQL_ECHO", "false").strip().lower() in {"1", "true", "yes", "on"}
