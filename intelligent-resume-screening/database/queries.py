"""All SQL used by the routes and report service. Every query is parameterised."""
import json
from typing import Any, Dict, List, Optional, Tuple

REVIEW_STATUSES = ("pending", "shortlisted", "on_hold", "not_selected")


def _j(value: Optional[str], default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------- jobs
def _job_dict(db, row) -> Dict:
    skills = db.execute("SELECT skill, weight FROM job_skills WHERE job_id=? ORDER BY weight DESC, skill",
                        (row["id"],)).fetchall()
    d = dict(row)
    d["skills"] = [{"skill": s["skill"], "weight": s["weight"]} for s in skills]
    d["weights_total"] = round(sum(s["weight"] for s in skills), 2)
    return d


def get_job(db, job_id: int) -> Optional[Dict]:
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _job_dict(db, row) if row else None


def list_jobs(db) -> List[Dict]:
    rows = db.execute("SELECT * FROM jobs ORDER BY updated_at DESC, id DESC").fetchall()
    return [_job_dict(db, r) for r in rows]


def save_job(db, data: Dict, job_id: Optional[int] = None) -> int:
    """Insert or update a job and replace its skills in one transaction."""
    with db:
        if job_id is None:
            cur = db.execute(
                "INSERT INTO jobs (title, description, min_experience_years, education_requirement, source) VALUES (?,?,?,?,?)",
                (data["title"], data["description"], data["min_experience_years"],
                 data["education_requirement"], data.get("source", "manual")))
            job_id = cur.lastrowid
        else:
            db.execute(
                """UPDATE jobs SET title=?, description=?, min_experience_years=?, education_requirement=?,
                   updated_at=datetime('now') WHERE id=?""",
                (data["title"], data["description"], data["min_experience_years"],
                 data["education_requirement"], job_id))
            db.execute("DELETE FROM job_skills WHERE job_id=?", (job_id,))
        db.executemany("INSERT INTO job_skills (job_id, skill, weight) VALUES (?,?,?)",
                       [(job_id, s["skill"], s["weight"]) for s in data["skills"]])
    return job_id


def delete_job(db, job_id: int) -> bool:
    with db:
        cur = db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return cur.rowcount > 0


# ----------------------------------------------------------------------------- sessions
def create_session(db, job: Dict) -> int:
    snapshot = {k: job[k] for k in ("title", "description", "min_experience_years", "education_requirement", "skills")}
    with db:
        cur = db.execute("INSERT INTO screening_sessions (job_id, job_title, job_snapshot) VALUES (?,?,?)",
                         (job["id"], job["title"], json.dumps(snapshot)))
    return cur.lastrowid


def delete_session(db, session_id: int) -> None:
    with db:
        db.execute("DELETE FROM screening_sessions WHERE id=?", (session_id,))


def get_session(db, session_id: int) -> Optional[Dict]:
    row = db.execute(_SESSION_SQL + " WHERE s.id=? GROUP BY s.id", (session_id,)).fetchone()
    return _session_dict(row) if row else None


_SESSION_SQL = """
SELECT s.id, s.job_id, s.job_title, s.job_snapshot, s.created_at,
       COUNT(r.id) AS total_files,
       SUM(CASE WHEN r.processing_status IN ('processed','processed_with_warnings') THEN 1 ELSE 0 END) AS processed,
       SUM(CASE WHEN r.processing_status='failed' THEN 1 ELSE 0 END) AS failed,
       (SELECT ROUND(AVG(sr.score),2) FROM screening_results sr WHERE sr.session_id=s.id) AS avg_score
FROM screening_sessions s LEFT JOIN resumes r ON r.session_id = s.id
"""


def _session_dict(row) -> Dict:
    d = dict(row)
    d["job_snapshot"] = _j(d.get("job_snapshot"), {})
    for k in ("processed", "failed"):
        d[k] = d[k] or 0
    return d


def list_sessions(db) -> List[Dict]:
    rows = db.execute(_SESSION_SQL + " GROUP BY s.id ORDER BY s.id DESC").fetchall()
    out = []
    for r in rows:
        d = _session_dict(r)
        d.pop("job_snapshot", None)
        out.append(d)
    return out


def session_failures(db, session_id: int) -> List[Dict]:
    rows = db.execute("SELECT original_filename, error_message FROM resumes WHERE session_id=? AND processing_status='failed'",
                      (session_id,)).fetchall()
    return [dict(r) for r in rows]


def session_has_hash(db, session_id: int, sha256: str) -> bool:
    return db.execute("SELECT 1 FROM resumes WHERE session_id=? AND sha256=?", (session_id, sha256)).fetchone() is not None


# ----------------------------------------------------------------------------- candidates
_CAND_SELECT = """
SELECT c.id AS candidate_id, c.name, c.email, c.phone, c.education, c.experience_years, c.experience_method,
       c.skills_json, sr.score, sr.matched_json, sr.missing_json, sr.needs_review, sr.review_reasons_json,
       sr.review_status, sr.reviewer_note, sr.reviewed_at,
       r.processing_status, r.original_filename, r.extraction_method, r.ocr_confidence, r.warnings_json,
       s.id AS session_id, s.job_title, s.created_at AS screened_at
FROM screening_results sr
JOIN candidates c ON c.id = sr.candidate_id
JOIN resumes r ON r.id = c.resume_id
JOIN screening_sessions s ON s.id = sr.session_id
"""

SORT_COLUMNS = {
    "score": "sr.score", "name": "c.name COLLATE NOCASE", "experience": "c.experience_years",
    "screened_at": "s.created_at", "review_status": "sr.review_status", "email": "c.email COLLATE NOCASE",
}


def _cand_dict(row) -> Dict:
    d = dict(row)
    d["skills"] = _j(d.pop("skills_json"), [])
    d["matched_skills"] = _j(d.pop("matched_json"), [])
    d["missing_skills"] = _j(d.pop("missing_json"), [])
    d["review_reasons"] = _j(d.pop("review_reasons_json"), [])
    d["warnings"] = _j(d.pop("warnings_json"), [])
    d["needs_review"] = bool(d["needs_review"])
    return d


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def query_candidates(db, *, q: Optional[str] = None, min_score: Optional[float] = None,
                     max_score: Optional[float] = None, status: Optional[str] = None,
                     review_status: Optional[str] = None, needs_review: Optional[bool] = None,
                     session_id: Optional[int] = None, job_id: Optional[int] = None,
                     sort: str = "score", order: str = "desc", page: int = 1,
                     per_page: Optional[int] = 10) -> Tuple[List[Dict], int]:
    where, params = [], []
    if q:
        like = _like(q.strip())
        where.append("(c.name LIKE ? ESCAPE '\\' OR c.email LIKE ? ESCAPE '\\' OR c.skills_json LIKE ? ESCAPE '\\' "
                     "OR r.original_filename LIKE ? ESCAPE '\\')")
        params += [like] * 4
    if min_score is not None:
        where.append("sr.score >= ?"); params.append(min_score)
    if max_score is not None:
        where.append("sr.score <= ?"); params.append(max_score)
    if status:
        where.append("r.processing_status = ?"); params.append(status)
    if review_status:
        where.append("sr.review_status = ?"); params.append(review_status)
    if needs_review is not None:
        where.append("sr.needs_review = ?"); params.append(1 if needs_review else 0)
    if session_id:
        where.append("s.id = ?"); params.append(session_id)
    if job_id:
        where.append("s.job_id = ?"); params.append(job_id)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.execute("SELECT COUNT(*) FROM screening_results sr JOIN candidates c ON c.id=sr.candidate_id "
                       "JOIN resumes r ON r.id=c.resume_id JOIN screening_sessions s ON s.id=sr.session_id" + clause,
                       params).fetchone()[0]
    sort_sql = SORT_COLUMNS.get(sort, SORT_COLUMNS["score"])
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    sql = _CAND_SELECT + clause + f" ORDER BY {sort_sql} {direction}, c.id ASC"
    if per_page:
        sql += " LIMIT ? OFFSET ?"
        params = params + [per_page, max(page - 1, 0) * per_page]
    return [_cand_dict(r) for r in db.execute(sql, params).fetchall()], total


def get_candidate_detail(db, candidate_id: int) -> Optional[Dict]:
    row = db.execute(_CAND_SELECT + " WHERE c.id = ?", (candidate_id,)).fetchone()
    if not row:
        return None
    d = _cand_dict(row)
    extra = db.execute(
        """SELECT r.id AS resume_id, r.extracted_text, r.page_count, r.file_size, sr.breakdown_json,
                  sr.requirement_checks_json, s.job_snapshot
           FROM candidates c JOIN resumes r ON r.id=c.resume_id
           JOIN screening_results sr ON sr.candidate_id=c.id JOIN screening_sessions s ON s.id=sr.session_id
           WHERE c.id=?""", (candidate_id,)).fetchone()
    d["extracted_text"] = extra["extracted_text"] or ""
    d["page_count"] = extra["page_count"]
    d["breakdown"] = _j(extra["breakdown_json"], [])
    d["requirement_checks"] = _j(extra["requirement_checks_json"], {})
    d["job_snapshot"] = _j(extra["job_snapshot"], {})
    logs = db.execute("SELECT level, message, created_at FROM processing_logs WHERE resume_id=? ORDER BY id",
                      (extra["resume_id"],)).fetchall()
    d["logs"] = [dict(x) for x in logs]
    return d


def update_review(db, candidate_id: int, review_status: Optional[str], note: Optional[str]) -> bool:
    sets, params = [], []
    if review_status is not None:
        sets.append("review_status=?"); params.append(review_status)
    if note is not None:
        sets.append("reviewer_note=?"); params.append(note)
    sets.append("reviewed_at=datetime('now')")
    with db:
        cur = db.execute(f"UPDATE screening_results SET {', '.join(sets)} WHERE candidate_id=?", params + [candidate_id])
    return cur.rowcount > 0


def delete_candidate(db, candidate_id: int) -> bool:
    """Data minimisation: remove a candidate and everything derived from the resume."""
    with db:
        row = db.execute("SELECT resume_id FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            return False
        db.execute("DELETE FROM resumes WHERE id=?", (row["resume_id"],))
    return True


# ----------------------------------------------------------------------------- dashboard
def dashboard_stats(db, high_threshold: float, review_threshold: float) -> Dict:
    one = lambda sql, p=(): db.execute(sql, p).fetchone()[0]
    total = one("SELECT COUNT(*) FROM resumes WHERE processing_status IN ('processed','processed_with_warnings')")
    failed = one("SELECT COUNT(*) FROM resumes WHERE processing_status='failed'")
    high = one("SELECT COUNT(*) FROM screening_results WHERE score >= ?", (high_threshold,))
    manual = one("SELECT COUNT(*) FROM screening_results WHERE needs_review=1 AND review_status='pending'")
    avg = one("SELECT AVG(score) FROM screening_results")
    bins = [0] * 5
    for (score,) in db.execute("SELECT score FROM screening_results"):
        bins[min(int(score // 20), 4)] += 1
    recent = [dict(r) for r in db.execute(
        """SELECT s.id, s.job_title, s.created_at, COUNT(r.id) AS files,
                  (SELECT ROUND(AVG(score),1) FROM screening_results WHERE session_id=s.id) AS avg_score
           FROM screening_sessions s LEFT JOIN resumes r ON r.session_id=s.id
           GROUP BY s.id ORDER BY s.id DESC LIMIT 8""")]
    return {
        "total_processed": total, "failed": failed, "high_match": high, "manual_review": manual,
        "average_score": round(avg, 1) if avg is not None else 0,
        "distribution": {"labels": ["0-19%", "20-39%", "40-59%", "60-79%", "80-100%"], "counts": bins},
        "recent_activity": recent,
        "thresholds": {"high_match": high_threshold, "review": review_threshold},
    }
