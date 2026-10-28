"""Application configuration. Values can be overridden with environment variables or a .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: Path) -> str:
    value = os.getenv(name)
    if not value:
        return str(default)
    p = Path(value)
    return str(p if p.is_absolute() else ROOT / p)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    BASE_DIR = str(ROOT)
    DATABASE_PATH = _path("DATABASE_PATH", ROOT / "database" / "screening.db")
    UPLOAD_FOLDER = _path("UPLOAD_FOLDER", ROOT / "uploads")
    OUTPUT_FOLDER = _path("OUTPUT_FOLDER", ROOT / "outputs")
    SKILLS_DICTIONARY_PATH = _path("SKILLS_DICTIONARY_PATH", ROOT / "data" / "skills_dictionary.json")

    # Upload limits
    MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "10"))
    MAX_FILES_PER_REQUEST = int(os.getenv("MAX_FILES_PER_REQUEST", "50"))
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "30"))
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # hard cap for a whole request
    ALLOWED_EXTENSIONS = {".pdf"}
    ALLOWED_MIME_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}

    # OCR
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
    OCR_ENABLED = _bool("OCR_ENABLED", True)
    OCR_DPI = int(os.getenv("OCR_DPI", "200"))
    OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "10"))
    OCR_LOW_CONFIDENCE = float(os.getenv("OCR_LOW_CONFIDENCE", "60"))
    MIN_TEXT_CHARS_PER_PAGE = int(os.getenv("MIN_TEXT_CHARS_PER_PAGE", "50"))

    # Scoring thresholds. These ONLY flag records for human review; nobody is rejected automatically.
    REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "50"))
    HIGH_MATCH_THRESHOLD = float(os.getenv("HIGH_MATCH_THRESHOLD", "70"))

    # Privacy: delete the uploaded PDF once its text has been extracted (extracted text is kept for review).
    KEEP_UPLOADED_FILES = _bool("KEEP_UPLOADED_FILES", False)

    JSON_SORT_KEYS = False
