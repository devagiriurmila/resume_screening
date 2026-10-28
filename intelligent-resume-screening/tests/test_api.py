import io

from tests.conftest import JOB
from tests.helpers import make_pdf


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok"


def test_job_crud_and_weight_normalisation(client):
    payload = dict(JOB, skills=[{"skill": "Microsoft Excel", "weight": 3}, {"skill": "py", "weight": 1}])
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 201
    job = r.get_json()["job"]
    assert job["weights_total"] == 100
    assert {s["skill"] for s in job["skills"]} == {"Excel", "Python"}  # aliases resolved to canonical names
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200
    upd = client.put(f"/api/jobs/{job['id']}", json=dict(payload, title="Renamed"))
    assert upd.get_json()["job"]["title"] == "Renamed"
    assert len(client.get("/api/jobs").get_json()["jobs"]) == 1
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 200
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_job_validation_errors(client):
    for bad in ({}, {"title": "x"}, {"title": "x", "skills": [{"skill": "A", "weight": -1}]},
                {"title": "x", "skills": [{"skill": "A", "weight": 1}, {"skill": "A", "weight": 2}]},
                {"title": "x", "min_experience_years": "abc", "skills": [{"skill": "A", "weight": 1}]}):
        r = client.post("/api/jobs", json=bad)
        assert r.status_code == 400 and "details" in r.get_json()
    assert client.post("/api/jobs", data="not json", content_type="text/plain").status_code == 400


def test_upload_and_results(client, uploaded):
    res = uploaded["results"][0]
    assert res["status"] in ("processed", "processed_with_warnings")
    # Python, SQL (via PostgreSQL), Excel (via Microsoft Excel), Communication -> all matched
    assert res["score"] == 100.0
    detail = client.get(f"/api/candidates/{res['candidate_id']}").get_json()["candidate"]
    assert detail["name"] == "Test Person" and detail["email"] == "test.person@example.com"
    assert "Python" in detail["extracted_text"] and len(detail["breakdown"]) == 4
    assert detail["review_status"] == "pending"


def test_upload_rejects_bad_files(client, job_id, tmp_path):
    def post(name, content, mime="application/pdf"):
        return client.post("/api/resumes/upload", content_type="multipart/form-data",
                           data={"job_id": job_id, "files": (io.BytesIO(content), name, mime)})
    assert post("notes.txt", b"hello", "text/plain").status_code == 422
    r = post("fake.pdf", b"just text")
    assert r.status_code == 422 and "PDF" in r.get_json()["results"][0]["error"]
    assert post("empty.pdf", b"").status_code == 422
    assert post("script.exe", b"MZ...", "application/octet-stream").status_code == 422
    # a rejected-only request must not leave an empty session behind
    assert client.get("/api/screenings").get_json()["screenings"] == []


def test_upload_requires_job_and_files(client, job_id):
    assert client.post("/api/resumes/upload", data={}).status_code == 400
    assert client.post("/api/resumes/upload", data={"job_id": 999}).status_code == 404
    assert client.post("/api/resumes/upload", data={"job_id": job_id}).status_code == 400


def test_size_limit(app, client, job_id):
    app.config["MAX_FILE_MB"] = 0  # anything non-empty is too big
    r = client.post("/api/resumes/upload", content_type="multipart/form-data",
                    data={"job_id": job_id, "files": (io.BytesIO(b"%PDF-1.4 x"), "a.pdf", "application/pdf")})
    assert r.status_code == 422 and "larger" in r.get_json()["results"][0]["error"]


def test_path_traversal_filename_is_neutralised(app, client, job_id, tmp_path):
    pdf = make_pdf(tmp_path / "x.pdf")
    with open(pdf, "rb") as fh:
        r = client.post("/api/resumes/upload", content_type="multipart/form-data",
                        data={"job_id": job_id, "files": (fh, "../../../evil.pdf", "application/pdf")})
    assert r.status_code == 201
    assert r.get_json()["results"][0]["filename"] == "evil.pdf"
    assert not (tmp_path.parent / "evil.pdf").exists()


def test_uploaded_file_deleted_after_processing_by_default(app, uploaded):
    import os
    assert os.listdir(app.config["UPLOAD_FOLDER"]) == []


def test_duplicate_in_same_session_rejected(client, job_id, uploaded, tmp_path):
    pdf = tmp_path / "good.pdf"  # same bytes as the file uploaded by the fixture
    with open(pdf, "rb") as fh:
        r = client.post("/api/resumes/upload", content_type="multipart/form-data",
                        data={"job_id": job_id, "session_id": uploaded["session_id"], "files": (fh, "again.pdf", "application/pdf")})
    assert r.get_json()["results"][0]["status"] == "rejected"


def test_candidate_listing_filters_sort_pagination(client, job_id, tmp_path):
    texts = {"Alpha One": "Alpha One\na@example.com\nSKILLS\nPython, SQL, Excel, communication skills",
             "Beta Two": "Beta Two\nb@example.com\nSKILLS\nExcel",
             "Gamma Three": "Gamma Three\nc@example.com\nSKILLS\nJava"}
    sid = None
    for name, text in texts.items():
        pdf = make_pdf(tmp_path / f"{name}.pdf", text)
        with open(pdf, "rb") as fh:
            data = {"job_id": job_id, "files": (fh, f"{name}.pdf", "application/pdf")}
            if sid:
                data["session_id"] = sid
            sid = client.post("/api/resumes/upload", data=data, content_type="multipart/form-data").get_json()["session_id"]
    allc = client.get("/api/candidates?sort=score&order=desc").get_json()
    assert allc["total"] == 3 and [c["name"] for c in allc["candidates"]] == ["Alpha One", "Beta Two", "Gamma Three"]
    assert client.get("/api/candidates?q=beta").get_json()["total"] == 1
    assert client.get("/api/candidates?min_score=50").get_json()["total"] == 1
    assert client.get("/api/candidates?sort=name&order=asc").get_json()["candidates"][0]["name"] == "Alpha One"
    page2 = client.get("/api/candidates?per_page=2&page=2").get_json()
    assert len(page2["candidates"]) == 1 and page2["pages"] == 2
    assert client.get("/api/candidates?min_score=abc").status_code == 400
    # SQL-injection style search text is treated as plain text
    assert client.get("/api/candidates?q=%27%3B%20DROP%20TABLE%20candidates%3B--").get_json()["total"] == 0
    assert client.get("/api/candidates").status_code == 200


def test_low_score_flags_review_but_never_rejects(client, uploaded):
    cid = uploaded["results"][0]["candidate_id"]
    r = client.post("/api/jobs", json=dict(JOB, title="Java job", skills=[{"skill": "Java", "weight": 1}])).get_json()["job"]
    pdf = None
    # low-score candidate for a different job
    import tempfile, os
    from tests.helpers import make_pdf as mk
    with tempfile.TemporaryDirectory() as d:
        p = mk(os.path.join(d, "low.pdf"))
        with open(p, "rb") as fh:
            res = client.post("/api/resumes/upload", content_type="multipart/form-data",
                              data={"job_id": r["id"], "files": (fh, "low.pdf", "application/pdf")}).get_json()["results"][0]
    detail = client.get(f"/api/candidates/{res['candidate_id']}").get_json()["candidate"]
    assert detail["score"] == 0 and detail["needs_review"] is True
    assert detail["review_status"] == "pending"  # not auto-rejected
    assert any("flag only" in x for x in detail["review_reasons"])


def test_review_patch_and_delete(client, uploaded):
    cid = uploaded["results"][0]["candidate_id"]
    r = client.patch(f"/api/candidates/{cid}/review", json={"review_status": "shortlisted", "note": "Good fit"})
    assert r.status_code == 200 and r.get_json()["candidate"]["review_status"] == "shortlisted"
    assert client.patch(f"/api/candidates/{cid}/review", json={}).status_code == 400
    assert client.patch(f"/api/candidates/{cid}/review", json={"review_status": "hired"}).status_code == 400
    assert client.patch("/api/candidates/999/review", json={"note": "x"}).status_code == 404
    assert client.delete(f"/api/candidates/{cid}").status_code == 200
    assert client.get(f"/api/candidates/{cid}").status_code == 404


def test_screenings_and_dashboard(client, uploaded):
    sid = uploaded["session_id"]
    lst = client.get("/api/screenings").get_json()["screenings"]
    assert lst[0]["id"] == sid and lst[0]["job_title"] == JOB["title"] and lst[0]["processed"] == 1
    detail = client.get(f"/api/screenings/{sid}").get_json()
    assert detail["screening"]["job_snapshot"]["skills"] and len(detail["candidates"]) == 1
    assert client.get("/api/screenings/999").status_code == 404
    stats = client.get("/api/dashboard").get_json()
    assert stats["total_processed"] == 1 and stats["high_match"] == 1 and sum(stats["distribution"]["counts"]) == 1


def test_pages_render(client, uploaded):
    cid = uploaded["results"][0]["candidate_id"]
    for path in ("/", "/jobs", "/jobs/new", "/jobs/1/edit", "/upload", "/candidates", f"/candidates/{cid}",
                 "/screenings", "/demo-job"):
        assert client.get(path).status_code == 200, path
    assert client.get("/candidates/999").status_code == 404
    assert client.get("/nope").status_code == 404
    assert client.get("/api/nope").get_json()["error"]
    assert "Test Person" in client.get(f"/candidates/{cid}").get_data(as_text=True)


def test_html_is_escaped(client, job_id, tmp_path):
    pdf = make_pdf(tmp_path / "x.pdf", "<script>alert(1)</script> Hacker\nh@example.com\nPython")
    with open(pdf, "rb") as fh:
        cid = client.post("/api/resumes/upload", content_type="multipart/form-data",
                          data={"job_id": job_id, "files": (fh, "x.pdf", "application/pdf")}).get_json()["results"][0]["candidate_id"]
    assert "<script>alert(1)</script>" not in client.get(f"/candidates/{cid}").get_data(as_text=True)
