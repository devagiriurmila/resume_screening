import pytest

from app import create_app
from tests.helpers import make_pdf

JOB = {
    "title": "Test Analyst",
    "description": "Fictional job",
    "min_experience_years": 1,
    "education_requirement": "Bachelor's degree",
    "skills": [{"skill": "Python", "weight": 40}, {"skill": "SQL", "weight": 25},
               {"skill": "Excel", "weight": 20}, {"skill": "Communication", "weight": 15}],
}


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE_PATH": str(tmp_path / "test.db"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "OUTPUT_FOLDER": str(tmp_path / "outputs"),
    })


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def job_id(client):
    resp = client.post("/api/jobs", json=JOB)
    assert resp.status_code == 201
    return resp.get_json()["job"]["id"]


@pytest.fixture()
def uploaded(client, job_id, tmp_path):
    """Upload one good resume and return the JSON response."""
    pdf = make_pdf(tmp_path / "good.pdf")
    with open(pdf, "rb") as fh:
        resp = client.post("/api/resumes/upload", data={"job_id": job_id, "files": (fh, "good.pdf", "application/pdf")},
                           content_type="multipart/form-data")
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()
