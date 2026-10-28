"""Extract years of experience and education only when reasonably reliable."""
import datetime as dt
import re
from typing import Dict, List, Optional

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

STATED_RE = re.compile(
    r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:[a-z/&,\- ]{0,40}?\s)?experience", re.I)
STATED_RE_2 = re.compile(r"experience\s*(?:of|:)?\s*(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I)

DATE = r"(?:(?P<{p}m>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+)?(?P<{p}y>(?:19|20)\d{{2}})"
RANGE_RE = re.compile(
    DATE.format(p="s") + r"\s*(?:-|–|—|to)\s*(?:(?P<present>present|current|now|till date|ongoing)|" + DATE.format(p="e") + ")",
    re.I)

SECTION_HEADERS = {
    "experience": {"experience", "work experience", "professional experience", "employment", "employment history",
                   "work history", "internships", "internship experience"},
    "other": {"education", "skills", "technical skills", "projects", "certifications", "summary", "profile",
              "objective", "achievements", "languages", "interests", "references", "awards", "academic projects",
              "personal details", "contact"},
}


def _experience_section(text: str) -> Optional[str]:
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower().rstrip(":") in SECTION_HEADERS["experience"]:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].strip().lower().rstrip(":") in SECTION_HEADERS["other"]:
            end = j
            break
    return "\n".join(lines[start:end])


def _month_index(year: int, month: Optional[str], default_month: int) -> int:
    return year * 12 + (MONTHS[month.lower()[:3]] if month else default_month) - 1


def extract_experience(text: str, today: Optional[dt.date] = None) -> Optional[Dict]:
    """Return {'years': float, 'method': 'stated' | 'estimated from dates'} or None."""
    if not text:
        return None
    today = today or dt.date.today()

    stated: List[float] = []
    for rx in (STATED_RE, STATED_RE_2):
        stated += [float(m.group(1)) for m in rx.finditer(text)]
    stated = [v for v in stated if 0 < v <= 45]
    if stated:
        return {"years": max(stated), "method": "stated"}

    section = _experience_section(text)
    if not section:
        return None
    spans = []
    for m in RANGE_RE.finditer(section):
        sy = int(m.group("sy"))
        start = _month_index(sy, m.group("sm"), 1)
        if m.group("present"):
            end = today.year * 12 + today.month - 1
        else:
            ey = int(m.group("ey"))
            end = _month_index(ey, m.group("em"), 12 if m.group("sm") or m.group("em") else 1)
            if not (m.group("sm") or m.group("em")):
                start = sy * 12  # year-only ranges: count whole-year difference
                end = ey * 12
        if end < start or (end - start) > 12 * 45 or sy > today.year + 1:
            continue
        spans.append((start, end))
    if not spans:
        return None
    spans.sort()
    merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    months = sum(e - s for s, e in merged)
    if months <= 0:
        return None
    return {"years": round(months / 12.0, 1), "method": "estimated from dates"}


# ----------------------------------------------------------------------------- education
EDU_PATTERNS = [
    (4, "Doctorate", re.compile(r"\bPh\.?\s?D\b|\bDoctorate\b", re.I)),
    (3, "Master's", re.compile(r"\bMaster(?:'s|s)?\b|\bM\.?\s?Tech\b|\bM\.E\.|\bM\.?\s?Sc\b|\bMCA\b|\bMBA\b|\bM\.?\s?Com\b", re.I)),
    (2, "Bachelor's", re.compile(r"\bBachelor(?:'s|s)?\b|\bB\.?\s?Tech\b|\bB\.E\.|\bB\.?\s?Sc\b|\bBCA\b|\bBBA\b|\bB\.?\s?Com\b", re.I)),
    (1, "Diploma", re.compile(r"\bDiploma\b", re.I)),
]
# Abbreviations like "BE"/"ME" are too ambiguous in normal words, so only dotted forms are accepted.


def education_level(text: str) -> int:
    """0 = not detected, 1 diploma, 2 bachelor, 3 master, 4 doctorate."""
    best = 0
    for level, _label, rx in EDU_PATTERNS:
        if rx.search(text or ""):
            best = max(best, level)
    return best


def extract_education(text: str) -> Optional[Dict]:
    """Return {'text': str, 'level': int} for the highest qualification line, or None."""
    best = None
    for ln in (text or "").splitlines():
        line = ln.strip()
        if not line or len(line) > 200:
            continue
        level = education_level(line)
        if level and (best is None or level > best["level"]):
            best = {"text": line, "level": level}
    return best
