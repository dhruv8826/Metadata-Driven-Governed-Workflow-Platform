import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = os.environ.get("SQLITE_PATH", str(BASE_DIR / "platform.db"))
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"
]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_PAYLOAD_BYTES = 1024 * 1024  # 1 MB
