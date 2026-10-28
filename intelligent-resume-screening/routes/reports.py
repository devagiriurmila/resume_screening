"""Dashboard statistics, screening sessions and report downloads."""
import os
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from database import queries
from database.db import get_db
from services import report_service

bp = Blueprint("reports_api", __name__)


@bp.get("/api/dashboard")
def dashboard():
    cfg = current_app.config
    return jsonify(queries.dashboard_stats(get_db(), cfg["HIGH_MATCH_THRESHOLD"], cfg["REVIEW_THRESHOLD"]))


@bp.get("/api/screenings")
def screenings():
    return jsonify({"screenings": queries.list_sessions(get_db())})


@bp.get("/api/screenings/<int:screening_id>")
def screening_detail(screening_id):
    db = get_db()
    session = queries.get_session(db, screening_id)
    if not session:
        return jsonify({"error": "Screening not found"}), 404
    rows, _ = queries.query_candidates(db, session_id=screening_id, per_page=None)
    return jsonify({"screening": session, "candidates": rows, "failures": queries.session_failures(db, screening_id)})


def _report_rows():
    """Resolve ?session_id= / ?job_id= into rows. Returns (rows, session, title, error_response)."""
    db = get_db()
    session_id = request.args.get("session_id", type=int)
    job_id = request.args.get("job_id", type=int)
    session = None
    if session_id:
        session = queries.get_session(db, session_id)
        if not session:
            return None, None, None, (jsonify({"error": "Screening not found"}), 404)
    rows, _ = queries.query_candidates(db, session_id=session_id, job_id=job_id, per_page=None)
    title = f"Screening #{session_id} - {session['job_title']}" if session else "All screenings"
    return rows, session, title, None


@bp.get("/api/reports/excel")
def excel_report():
    rows, session, title, err = _report_rows()
    if err:
        return err
    if not rows:
        return jsonify({"error": "No screening results to export yet."}), 404
    db = get_db()
    breakdowns = {r["candidate_id"]: queries.get_candidate_detail(db, r["candidate_id"])["breakdown"] for r in rows}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"screening_report_{('session' + str(session['id'])) if session else 'all'}_{stamp}.xlsx"
    path = os.path.join(current_app.config["OUTPUT_FOLDER"], name)
    report_service.build_excel(rows, breakdowns, path, title, current_app.config["HIGH_MATCH_THRESHOLD"])
    return send_file(path, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.get("/api/reports/csv")
def csv_report():
    rows, session, _title, err = _report_rows()
    if err:
        return err
    if not rows:
        return jsonify({"error": "No screening results to export yet."}), 404
    name = f"screening_{('session' + str(session['id'])) if session else 'all'}.csv"
    return Response(report_service.build_csv(rows), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}"})


@bp.get("/api/reports/summary")
def summary_report():
    rows, session, title, err = _report_rows()
    if err:
        return err
    text = report_service.build_summary_text(rows, title, current_app.config["HIGH_MATCH_THRESHOLD"], session)
    return Response(text, mimetype="text/plain",
                    headers={"Content-Disposition": "attachment; filename=screening_summary.txt"})
