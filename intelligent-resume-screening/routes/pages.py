"""HTML pages (server-rendered with Jinja2, which auto-escapes all dynamic text)."""
import os

from flask import Blueprint, abort, current_app, render_template, send_from_directory

from database import queries
from database.db import get_db
from services.skill_matcher import SCORING_LIMITATIONS

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/jobs")
def jobs():
    return render_template("jobs.html", jobs=queries.list_jobs(get_db()))


@bp.get("/jobs/new")
def job_new():
    return render_template("job_form.html", job=None)


@bp.get("/jobs/<int:job_id>/edit")
def job_edit(job_id):
    job = queries.get_job(get_db(), job_id)
    if not job:
        abort(404)
    return render_template("job_form.html", job=job)


@bp.get("/upload")
def upload():
    return render_template("upload.html", jobs=queries.list_jobs(get_db()))


@bp.get("/candidates")
def candidates():
    db = get_db()
    return render_template("candidates.html", sessions=queries.list_sessions(db))


@bp.get("/candidates/<int:candidate_id>")
def candidate(candidate_id):
    detail = queries.get_candidate_detail(get_db(), candidate_id)
    if not detail:
        abort(404)
    return render_template("candidate_detail.html", c=detail, limitations=SCORING_LIMITATIONS,
                           statuses=queries.REVIEW_STATUSES)


@bp.get("/screenings")
def screenings():
    return render_template("screenings.html", sessions=queries.list_sessions(get_db()))


@bp.get("/demo-job")
def demo_job():
    """Serves the local demo job page that the Selenium scraper reads."""
    folder = os.path.join(current_app.config["BASE_DIR"], "scraper")
    return send_from_directory(folder, "demo_job_page.html")
