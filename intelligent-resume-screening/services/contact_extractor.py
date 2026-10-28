"""Extract e-mail, phone number and candidate name using conservative patterns.

If something cannot be found with reasonable confidence the functions return None
(the UI then shows 'Not detected'). Nothing is guessed.
"""
import re
from typing import Optional

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_CANDIDATE_RE = re.compile(r"(?<![\w.])(\+?\(?\d[\d\s().\-]{8,18}\d)(?![\w])")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")

NAME_STOP_WORDS = {
    "resume", "curriculum", "vitae", "cv", "profile", "summary", "objective", "contact", "address",
    "engineer", "analyst", "developer", "manager", "intern", "student", "designer", "scientist",
    "consultant", "executive", "administrator", "specialist", "officer", "fresher", "experience",
    "education", "skills", "page", "email", "phone", "mobile", "linkedin", "github", "fictional",
    "sample", "candidate", "about", "career", "technical", "professional",
}


def extract_email(text: str) -> Optional[str]:
    m = EMAIL_RE.search(text or "")
    return m.group(0).rstrip(".").lower() if m else None


def extract_phone(text: str) -> Optional[str]:
    for m in PHONE_CANDIDATE_RE.finditer(text or ""):
        raw = m.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        if not 10 <= len(digits) <= 13:
            continue
        # Reject strings made only of years / date ranges such as "2018 2020 2022"
        if len(YEAR_RE.findall(raw)) >= 2 and len(re.sub(r"[\s\-–./]", "", raw)) == 4 * len(YEAR_RE.findall(raw)):
            continue
        return re.sub(r"\s+", " ", raw)
    return None


def extract_name(text: str) -> Optional[str]:
    """Look for 'Name: ...' or a plain 2-4 word capitalised line near the top."""
    if not text:
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:15]:
        m = re.match(r"(?i)^(?:candidate\s+)?name\s*[:\-]\s*(.+)$", ln)
        if m and _looks_like_name(m.group(1)):
            return _tidy_name(m.group(1))
    for ln in lines[:8]:
        if _looks_like_name(ln):
            return _tidy_name(ln)
    return None


def _looks_like_name(line: str) -> bool:
    if "@" in line or re.search(r"\d", line) or re.search(r"https?://|www\.", line, re.I):
        return False
    tokens = line.split()
    if not 2 <= len(tokens) <= 4:
        return False
    for tok in tokens:
        if tok.lower().strip(".,") in NAME_STOP_WORDS:
            return False
        if not re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", tok):
            return False
        if not (tok[0].isupper()):
            return False
    return True


def _tidy_name(line: str) -> str:
    name = " ".join(line.split())
    return name.title() if name.isupper() else name
