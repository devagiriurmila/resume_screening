"""Candidate listing, detail and human review API."""
from flask import Blueprint, current_app, jsonify, request

from database import queries
from database.db import get_db

bp = Blueprint("candidates_api", __name__)


def _opt_float(name):
    val = request.args.get(name)
    if val in (None, ""):
        return None
    try:
        return float(val)
    except ValueError:
        raise ValueError(f"'{name}' must be a number")


@bp.get("/api/candidates")
def list_candidates():
    try:
        min_score, max_score = _opt_float("min_score"), _opt_float("max_score")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per_page = min(max(request.args.get("per_page", 10, type=int) or 10, 1), 100)
    needs = request.args.get("needs_review")
    rows, total = queries.query_candidates(
        get_db(), q=request.args.get("q"), min_score=min_score, max_score=max_score,
        status=request.args.get("status") or None, review_status=request.args.get("review_status") or None,
        needs_review=None if needs in (None, "") else needs in ("1", "true", "yes"),
        session_id=request.args.get("session_id", type=int), job_id=request.args.get("job_id", type=int),
        sort=request.args.get("sort", "score"), order=request.args.get("order", "desc"),
        page=page, per_page=per_page)
    return jsonify({"candidates": rows, "total": total, "page": page, "per_page": per_page,
                    "pages": max((total + per_page - 1) // per_page, 1)})


@bp.get("/api/candidates/<int:candidate_id>")
def candidate_detail(candidate_id):
    detail = queries.get_candidate_detail(get_db(), candidate_id)
    if not detail:
        return jsonify({"error": "Candidate not found"}), 404
    return jsonify({"candidate": detail})


@bp.patch("/api/candidates/<int:candidate_id>/review")
def review(candidate_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body required"}), 400
    status, note = data.get("review_status"), data.get("note")
    if status is None and note is None:
        return jsonify({"error": "Provide 'review_status' and/or 'note'"}), 400
    if status is not None and status not in queries.REVIEW_STATUSES:
        return jsonify({"error": f"review_status must be one of {list(queries.REVIEW_STATUSES)}"}), 400
    if note is not None:
        if not isinstance(note, str) or len(note) > 2000:
            return jsonify({"error": "note must be a string of at most 2000 characters"}), 400
    db = get_db()
    if not queries.update_review(db, candidate_id, status, note):
        return jsonify({"error": "Candidate not found"}), 404
    return jsonify({"candidate": queries.get_candidate_detail(db, candidate_id)})


@bp.delete("/api/candidates/<int:candidate_id>")
def delete_candidate(candidate_id):
    if not queries.delete_candidate(get_db(), candidate_id):
        return jsonify({"error": "Candidate not found"}), 404
    return jsonify({"deleted": candidate_id})
