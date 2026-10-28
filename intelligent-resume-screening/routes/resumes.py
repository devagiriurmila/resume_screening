"""Resume upload API: validates files, stores them under random names, runs the engine."""
import hashlib
import os
import uuid

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from database import queries
from database.db import get_db
from services.pipeline import process_and_store
from services.resume_parser import is_pdf_file

bp = Blueprint("resumes_api", __name__)


def _save_validated(file_storage, cfg):
    """Validate and save one upload. Returns (path, stored_name, display_name, sha256, size, error)."""
    display = secure_filename(file_storage.filename or "") or "resume.pdf"
    ext = os.path.splitext(display)[1].lower()
    if ext not in cfg["ALLOWED_EXTENSIONS"]:
        return None, None, display, None, 0, f"Unsupported file type '{ext or 'none'}'. Only PDF files are accepted."
    mime = (file_storage.mimetype or "").lower()
    if mime not in cfg["ALLOWED_MIME_TYPES"]:
        return None, None, display, None, 0, f"Unsupported content type '{mime}'."

    stored = uuid.uuid4().hex + ".pdf"  # client file name is never used for the path -> no path traversal
    path = os.path.join(cfg["UPLOAD_FOLDER"], stored)
    limit = cfg["MAX_FILE_MB"] * 1024 * 1024
    sha, size = hashlib.sha256(), 0
    try:
        with open(path, "wb") as out:
            while True:
                chunk = file_storage.stream.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise ValueError(f"File is larger than {cfg['MAX_FILE_MB']} MB.")
                sha.update(chunk)
                out.write(chunk)
        if size == 0:
            raise ValueError("File is empty.")
        if not is_pdf_file(path):
            raise ValueError("File content is not a real PDF (missing %PDF signature).")
    except ValueError as exc:
        _remove(path)
        return None, None, display, None, size, str(exc)
    return path, stored, display, sha.hexdigest(), size, None


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


@bp.post("/api/resumes/upload")
def upload():
    cfg = current_app.config
    db = get_db()
    job_id = request.form.get("job_id", type=int)
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    job = queries.get_job(db, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    files = [f for f in request.files.getlist("files") if f and f.filename is not None]
    if not files:
        return jsonify({"error": "No files uploaded. Send PDF files in the 'files' field."}), 400
    if len(files) > cfg["MAX_FILES_PER_REQUEST"]:
        return jsonify({"error": f"Too many files (max {cfg['MAX_FILES_PER_REQUEST']} per request)."}), 400

    session_id = request.form.get("session_id", type=int)
    created_new = not session_id
    if session_id:
        session = queries.get_session(db, session_id)
        if not session or session["job_id"] != job_id:
            return jsonify({"error": "session_id does not belong to this job"}), 404
    else:
        session_id = queries.create_session(db, job)

    results = []
    for f in files:
        path, stored, display, sha, size, error = _save_validated(f, cfg)
        if error:
            results.append({"filename": display, "status": "rejected", "error": error})
            continue
        if queries.session_has_hash(db, session_id, sha):
            _remove(path)
            results.append({"filename": display, "status": "rejected",
                            "error": "Duplicate file already processed in this session."})
            continue
        keep = cfg["KEEP_UPLOADED_FILES"]
        try:
            res = process_and_store(db, cfg, session_id=session_id, job=job, path=path, original_filename=display,
                                    sha256=sha, size=size, stored_filename=stored if keep else None)
        finally:
            if not keep:
                _remove(path)
        results.append(res)

    ok = [r for r in results if r["status"] in ("processed", "processed_with_warnings")]
    if created_new and all(r["status"] == "rejected" for r in results):
        queries.delete_session(db, session_id)  # nothing was screened; do not leave an empty session behind
        session_id = None
    summary = {"total": len(results), "processed": len(ok),
               "failed": sum(1 for r in results if r["status"] == "failed"),
               "rejected": sum(1 for r in results if r["status"] == "rejected")}
    code = 201 if ok else 422
    return jsonify({"session_id": session_id, "summary": summary, "results": results}), code
