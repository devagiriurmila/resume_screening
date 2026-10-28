"""Intelligent Resume Screening and Candidate Shortlisting System - Flask application."""
import logging
import os

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from config import Config
from database import db as database
from routes import candidates, jobs, pages, reports, resumes
from services import ocr_service


def create_app(overrides=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database.init_app(app)
    ocr_path = ocr_service.configure(app.config["TESSERACT_CMD"]) if app.config["OCR_ENABLED"] else None
    app.config["OCR_AVAILABLE"] = bool(ocr_path)
    app.logger.info("Tesseract OCR: %s", ocr_path or "NOT FOUND (scanned PDFs will be flagged)")

    for module in (jobs, resumes, candidates, reports, pages):
        app.register_blueprint(module.bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "ocr_available": app.config["OCR_AVAILABLE"],
                        "database": os.path.basename(app.config["DATABASE_PATH"])})

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        return resp

    @app.errorhandler(HTTPException)
    def http_error(err):
        if request.path.startswith("/api/"):
            message = "File too large" if err.code == 413 else err.description
            return jsonify({"error": message}), err.code
        return render_template("error.html", code=err.code, message=err.description), err.code

    @app.errorhandler(Exception)
    def server_error(err):
        app.logger.exception("Unhandled error")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("error.html", code=500, message="Something went wrong."), 500

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
