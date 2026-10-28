"""Job description REST API."""
from flask import Blueprint, current_app, jsonify, request

from database import queries
from database.db import get_db
from services.skill_matcher import get_dictionary, normalize_weights

bp = Blueprint("jobs_api", __name__)


def validate_job_payload(data):
    """Return (clean_dict, errors). Weights are normalised to total exactly 100."""
    errors = {}
    if not isinstance(data, dict):
        return None, {"body": "JSON object expected."}
    title = str(data.get("title", "")).strip()
    if not title:
        errors["title"] = "Job title is required."
    elif len(title) > 150:
        errors["title"] = "Job title must be 150 characters or fewer."
    description = str(data.get("description", "") or "").strip()
    if len(description) > 10000:
        errors["description"] = "Description is too long (10,000 characters max)."
    try:
        min_exp = float(data.get("min_experience_years") or 0)
        if min_exp < 0 or min_exp > 50:
            raise ValueError
    except (TypeError, ValueError):
        errors["min_experience_years"] = "Minimum experience must be a number between 0 and 50."
        min_exp = 0
    education = str(data.get("education_requirement", "") or "").strip()
    if len(education) > 200:
        errors["education_requirement"] = "Education requirement is too long."

    skills = []
    raw = data.get("skills")
    if not isinstance(raw, list) or not raw:
        errors["skills"] = "At least one required skill is needed."
    else:
        try:
            dictionary = get_dictionary(current_app.config.get("SKILLS_DICTIONARY_PATH"))
            prepared = []
            for item in raw:
                if not isinstance(item, dict):
                    raise ValueError("Each skill must be an object with 'skill' and 'weight'.")
                name = str(item.get("skill", "")).strip()
                prepared.append({"skill": dictionary.canonical(name) or name, "weight": item.get("weight")})
            skills = normalize_weights(prepared)
        except ValueError as exc:
            errors["skills"] = str(exc)
    if errors:
        return None, errors
    return {"title": title, "description": description, "min_experience_years": min_exp,
            "education_requirement": education, "skills": skills,
            "source": str(data.get("source", "manual"))[:30]}, {}


@bp.get("/api/jobs")
def list_jobs():
    return jsonify({"jobs": queries.list_jobs(get_db())})


@bp.post("/api/jobs")
def create_job():
    clean, errors = validate_job_payload(request.get_json(silent=True))
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    db = get_db()
    job_id = queries.save_job(db, clean)
    return jsonify({"job": queries.get_job(db, job_id), "message": "Weights were normalised to total 100%."}), 201


@bp.get("/api/jobs/<int:job_id>")
def get_job(job_id):
    job = queries.get_job(get_db(), job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job": job})


@bp.put("/api/jobs/<int:job_id>")
def update_job(job_id):
    db = get_db()
    if not queries.get_job(db, job_id):
        return jsonify({"error": "Job not found"}), 404
    clean, errors = validate_job_payload(request.get_json(silent=True))
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    queries.save_job(db, clean, job_id)
    return jsonify({"job": queries.get_job(db, job_id)})


@bp.delete("/api/jobs/<int:job_id>")
def delete_job(job_id):
    if not queries.delete_job(get_db(), job_id):
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"deleted": job_id})
