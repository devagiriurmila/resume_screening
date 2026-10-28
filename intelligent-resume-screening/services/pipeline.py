"""Orchestrates: extract text -> parse fields -> match skills -> store results.

`screen_pdf` is a pure function (no database) so it is easy to test and reuse.
`process_and_store` wraps it with database writes and processing logs.
"""
import json
import logging
from typing import Optional

from services.experience_extractor import education_level
from services.resume_parser import ResumeParseError, extract_text, parse_fields
from services.skill_matcher import extract_skills, get_dictionary, score_resume

log = logging.getLogger(__name__)


def requirement_checks(job: dict, fields: dict) -> dict:
    """Informational checks of experience/education requirements. They do NOT change the score."""
    checks = {}
    min_exp = float(job.get("min_experience_years") or 0)
    if min_exp > 0:
        years = fields.get("experience_years")
        if years is None:
            status, note = "unconfirmed", "Years of experience could not be reliably detected."
        elif years >= min_exp:
            status, note = "met", f"Detected {years} years ({fields.get('experience_method')})."
        else:
            status, note = "not_met", f"Detected {years} years ({fields.get('experience_method')}); a recruiter should verify."
        checks["experience"] = {"required": min_exp, "detected": years, "status": status, "note": note}
    edu_req = (job.get("education_requirement") or "").strip()
    if edu_req:
        req_level, got = education_level(edu_req), fields.get("education_level", 0)
        if req_level == 0:
            status, note = "unconfirmed", "The education requirement text was not recognised automatically."
        elif got == 0:
            status, note = "unconfirmed", "Education could not be detected in the resume."
        elif got >= req_level:
            status, note = "met", f"Detected: {fields.get('education')}"
        else:
            status, note = "not_met", f"Detected: {fields.get('education')}; a recruiter should verify."
        checks["education"] = {"required": edu_req, "detected": fields.get("education"), "status": status, "note": note}
    return checks


def review_reasons(config, outcome: dict) -> list:
    """Reasons a human should look closely. These are flags only; nothing is rejected automatically."""
    reasons = []
    if outcome["score"] < config["REVIEW_THRESHOLD"]:
        reasons.append(f"Skill-match score below {config['REVIEW_THRESHOLD']:g}% (flag only - not a rejection).")
    conf = outcome.get("ocr_confidence")
    if outcome["extraction_method"] in ("ocr", "mixed") and (conf is None or conf < config["OCR_LOW_CONFIDENCE"]):
        reasons.append("OCR confidence is low or unknown; the extracted text may be wrong.")
    if not outcome["fields"]["email"] and not outcome["fields"]["phone"]:
        reasons.append("No contact details detected.")
    if not outcome["detected_skills"]:
        reasons.append("No known skills detected in the text.")
    if len(outcome["text"]) < 200:
        reasons.append("Very little text extracted.")
    return reasons


def screen_pdf(path: str, job: dict, config) -> dict:
    """Run the full engine on one PDF and return a plain dict of results. Raises ResumeParseError."""
    dictionary = get_dictionary(config.get("SKILLS_DICTIONARY_PATH"))
    ext = extract_text(
        path,
        ocr_enabled=config["OCR_ENABLED"], ocr_dpi=config["OCR_DPI"], ocr_max_pages=config["OCR_MAX_PAGES"],
        min_chars_per_page=config["MIN_TEXT_CHARS_PER_PAGE"], tesseract_cmd=config["TESSERACT_CMD"],
        max_pages=config["MAX_PDF_PAGES"],
    )
    fields = parse_fields(ext.text)
    detected = extract_skills(ext.text, dictionary)
    scoring = score_resume(ext.text, job["skills"], dictionary)
    outcome = {
        "text": ext.text,
        "page_count": ext.page_count,
        "extraction_method": ext.method,
        "ocr_confidence": ext.ocr_confidence,
        "warnings": list(ext.warnings),
        "fields": fields,
        "detected_skills": [d["skill"] for d in detected],
        "score": scoring["score"],
        "matched": scoring["matched"],
        "missing": scoring["missing"],
        "breakdown": scoring["breakdown"],
        "requirement_checks": requirement_checks(job, fields),
    }
    outcome["review_reasons"] = review_reasons(config, outcome)
    return outcome


def _log(db, session_id, resume_id, level, message):
    db.execute("INSERT INTO processing_logs (session_id, resume_id, level, message) VALUES (?,?,?,?)",
               (session_id, resume_id, level, message))


def process_and_store(db, config, *, session_id: int, job: dict, path: str, original_filename: str,
                      sha256: str, size: int, stored_filename: Optional[str]) -> dict:
    """Process one stored PDF and persist everything. Always returns a result dict (never raises)."""
    with db:
        cur = db.execute(
            "INSERT INTO resumes (session_id, original_filename, stored_filename, sha256, file_size) VALUES (?,?,?,?,?)",
            (session_id, original_filename, stored_filename, sha256, size))
        resume_id = cur.lastrowid
        _log(db, session_id, resume_id, "INFO", f"Received '{original_filename}' ({size} bytes).")

    try:
        out = screen_pdf(path, job, config)
    except ResumeParseError as exc:
        return _fail(db, session_id, resume_id, original_filename, str(exc))
    except Exception as exc:  # defensive: one bad file must never stop the batch
        log.exception("Unexpected error while processing %s", original_filename)
        return _fail(db, session_id, resume_id, original_filename, f"Unexpected processing error: {exc}")

    status = "processed_with_warnings" if out["warnings"] else "processed"
    f = out["fields"]
    with db:
        db.execute(
            """UPDATE resumes SET page_count=?, extraction_method=?, ocr_confidence=?, extracted_text=?,
               warnings_json=?, processing_status=? WHERE id=?""",
            (out["page_count"], out["extraction_method"], out["ocr_confidence"], out["text"],
             json.dumps(out["warnings"]), status, resume_id))
        cand = db.execute(
            """INSERT INTO candidates (resume_id, name, email, phone, education, experience_years,
               experience_method, skills_json) VALUES (?,?,?,?,?,?,?,?)""",
            (resume_id, f["name"], f["email"], f["phone"], f["education"], f["experience_years"],
             f["experience_method"], json.dumps(out["detected_skills"])))
        candidate_id = cand.lastrowid
        db.execute(
            """INSERT INTO screening_results (session_id, candidate_id, score, matched_json, missing_json,
               breakdown_json, requirement_checks_json, needs_review, review_reasons_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (session_id, candidate_id, out["score"], json.dumps(out["matched"]), json.dumps(out["missing"]),
             json.dumps(out["breakdown"]), json.dumps(out["requirement_checks"]),
             1 if out["review_reasons"] else 0, json.dumps(out["review_reasons"])))
        _log(db, session_id, resume_id, "INFO",
             f"Text extracted via {out['extraction_method']}"
             + (f" (OCR confidence {out['ocr_confidence']}%)" if out["ocr_confidence"] is not None else "") + ".")
        for w in out["warnings"]:
            _log(db, session_id, resume_id, "WARNING", w)
        _log(db, session_id, resume_id, "INFO", f"Skill-match score {out['score']}%.")
    return {
        "filename": original_filename, "status": status, "candidate_id": candidate_id, "resume_id": resume_id,
        "name": f["name"], "score": out["score"], "needs_review": bool(out["review_reasons"]),
        "warnings": out["warnings"], "error": None,
    }


def _fail(db, session_id, resume_id, filename, message):
    with db:
        db.execute("UPDATE resumes SET processing_status='failed', error_message=?, extraction_method='none' WHERE id=?",
                   (message, resume_id))
        _log(db, session_id, resume_id, "ERROR", message)
    return {"filename": filename, "status": "failed", "candidate_id": None, "resume_id": resume_id,
            "name": None, "score": None, "needs_review": True, "warnings": [], "error": message}
