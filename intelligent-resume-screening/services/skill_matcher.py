"""Deterministic, explainable skill matching and weighted scoring.

Skill Match Score = sum of the (normalized) weights of the required skills found in the resume.
Nothing here uses machine learning, personal attributes, or hidden factors.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "skills_dictionary.json"

SCORING_LIMITATIONS = [
    "The score only measures how many of the recruiter-defined required skills are mentioned in the resume text.",
    "It does not measure skill depth, quality of work, personality, intelligence, or future job performance.",
    "A skill is counted when the skill name or a configured alias appears as a whole word; mentions are not verified.",
    "Skills that are phrased differently from the dictionary or aliases may be missed (shown as 'unconfirmed').",
    "Scanned resumes depend on OCR quality; OCR mistakes can hide or distort skills.",
    "Age, gender, photograph, caste, religion, disability and other sensitive attributes are never used.",
    "Scores never reject anyone. Thresholds only flag records for human review.",
]


# ----------------------------------------------------------------------------- dictionary
class SkillDictionary:
    def __init__(self, data: dict):
        self.skills: Dict[str, dict] = {}
        self.lookup: Dict[str, str] = {}
        for canonical, spec in data.get("skills", {}).items():
            aliases = [a.lower() for a in spec.get("aliases", [])]
            context = {k.lower(): [c.lower() for c in v] for k, v in spec.get("context_aliases", {}).items()}
            self.skills[canonical] = {"aliases": aliases, "context": context}
            self.lookup[canonical.lower()] = canonical
            for alias in list(aliases) + list(context):
                self.lookup.setdefault(alias, canonical)  # context aliases (e.g. 'py') also resolve to the skill

    @classmethod
    def from_file(cls, path: Optional[str] = None) -> "SkillDictionary":
        with open(path or DEFAULT_DICTIONARY_PATH, "r", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def canonical(self, name: str) -> Optional[str]:
        return self.lookup.get(_clean_name(name))

    def terms(self, name: str) -> Tuple[str, List[str], Dict[str, List[str]]]:
        """Return (canonical name, plain terms, context terms) for a skill name."""
        canon = self.canonical(name)
        if canon:
            spec = self.skills[canon]
            return canon, [canon.lower()] + spec["aliases"], spec["context"]
        clean = _clean_name(name)
        return name.strip(), [clean], {}


@lru_cache(maxsize=4)
def get_dictionary(path: Optional[str] = None) -> SkillDictionary:
    return SkillDictionary.from_file(path)


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


# ----------------------------------------------------------------------------- matching
@lru_cache(maxsize=4096)
def _term_regex(term: str) -> "re.Pattern":
    """Whole-word regex. Handles C++, C#, Node.js and multi-word terms; never matches inside other words."""
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", term.strip().lower()) if p]
    body = r"[\s\-]+".join(parts)
    return re.compile(r"(?<![a-z0-9+#_.])" + body + r"(?![a-z0-9+#_])(?!\.[a-z0-9])")


def normalize_for_matching(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _snippet(norm_text: str, match: "re.Match", radius: int = 35) -> str:
    start, end = max(0, match.start() - radius), min(len(norm_text), match.end() + radius)
    return ("..." if start else "") + norm_text[start:end].strip() + ("..." if end < len(norm_text) else "")


def find_skill_evidence(norm_text: str, name: str, dictionary: SkillDictionary) -> Optional[dict]:
    """Return {'term', 'snippet', 'note'} for the first piece of evidence, or None."""
    _canon, terms, context = dictionary.terms(name)
    for term in terms:
        m = _term_regex(term).search(norm_text)
        if m:
            return {"term": term, "snippet": _snippet(norm_text, m), "note": ""}
    for term, ctx_words in context.items():
        m = _term_regex(term).search(norm_text)
        if not m:
            continue
        for word in ctx_words:
            if _term_regex(word).search(norm_text):
                return {"term": term, "snippet": _snippet(norm_text, m), "note": f"accepted because '{word}' also appears"}
    return None


def extract_skills(text: str, dictionary: SkillDictionary) -> List[dict]:
    """Find every dictionary skill mentioned in the text."""
    norm = normalize_for_matching(text)
    found = []
    for canonical in dictionary.skills:
        ev = find_skill_evidence(norm, canonical, dictionary)
        if ev:
            found.append({"skill": canonical, **ev})
    return found


# ----------------------------------------------------------------------------- weights
def normalize_weights(items: List[dict]) -> List[dict]:
    """Validate and scale weights so they sum to exactly 100.

    items: [{'skill': str, 'weight': number | None}, ...]
    If no weights are supplied they are split equally. Raises ValueError on invalid input.
    """
    if not items:
        raise ValueError("At least one required skill is needed.")
    cleaned, seen = [], set()
    for item in items:
        name = re.sub(r"\s+", " ", str(item.get("skill", "")).strip())
        if not name:
            raise ValueError("Skill names cannot be empty.")
        key = name.lower()
        if key in seen:
            raise ValueError(f"Duplicate skill: {name}")
        seen.add(key)
        raw = item.get("weight")
        if raw in (None, ""):
            weight = None
        else:
            try:
                weight = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Weight for '{name}' must be a number.")
            if weight != weight or weight in (float("inf"), float("-inf")):
                raise ValueError(f"Weight for '{name}' must be a finite number.")
            if weight <= 0:
                raise ValueError(f"Weight for '{name}' must be greater than 0.")
        cleaned.append({"skill": name, "weight": weight})

    if all(c["weight"] is None for c in cleaned):
        for c in cleaned:
            c["weight"] = 1.0
    elif any(c["weight"] is None for c in cleaned):
        raise ValueError("Give every skill a weight, or leave all weights empty for an equal split.")

    total = sum(c["weight"] for c in cleaned)
    result = [{"skill": c["skill"], "weight": round(c["weight"] * 100.0 / total, 2)} for c in cleaned]
    diff = round(100.0 - sum(r["weight"] for r in result), 2)
    if diff:
        max(result, key=lambda r: r["weight"])["weight"] = round(max(result, key=lambda r: r["weight"])["weight"] + diff, 2)
    return result


# ----------------------------------------------------------------------------- scoring
def score_resume(text: str, job_skills: List[dict], dictionary: Optional[SkillDictionary] = None) -> dict:
    """Score resume text against weighted job skills.

    Returns {'score', 'matched', 'missing', 'breakdown', 'weights_total'}.
    """
    dictionary = dictionary or get_dictionary()
    weights = normalize_weights(job_skills)
    norm = normalize_for_matching(text)
    breakdown, matched, missing = [], [], []
    for item in weights:
        ev = find_skill_evidence(norm, item["skill"], dictionary)
        points = item["weight"] if ev else 0.0
        row = {
            "skill": item["skill"],
            "weight": item["weight"],
            "matched": bool(ev),
            "points": round(points, 2),
            "evidence": ev["term"] if ev else None,
            "snippet": ev["snippet"] if ev else None,
            "note": ev["note"] if ev else "",
        }
        breakdown.append(row)
        (matched if ev else missing).append(row["skill"])
    score = min(100.0, round(sum(r["points"] for r in breakdown), 2))
    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "breakdown": breakdown,
        "weights_total": round(sum(w["weight"] for w in weights), 2),
    }
