# REST API reference

Base URL: `http://127.0.0.1:5000`. All API responses are JSON (except downloads). Errors look like
`{"error": "message"}` (validation errors add `"details": {...}`). The API is intended for local use only; it has no
authentication and must not be exposed to the internet as-is.

| Method | Path | Purpose | Success | Common errors |
|--------|------|---------|---------|---------------|
| GET | `/api/health` | Liveness + whether Tesseract was found | 200 | - |
| GET | `/api/jobs` | List jobs with skills/weights | 200 | - |
| POST | `/api/jobs` | Create job (weights auto-normalised to 100) | 201 | 400 |
| GET | `/api/jobs/<id>` | One job | 200 | 404 |
| PUT | `/api/jobs/<id>` | Replace job fields and skills | 200 | 400, 404 |
| DELETE | `/api/jobs/<id>` | Delete job (past sessions keep a snapshot) | 200 | 404 |
| POST | `/api/resumes/upload` | Upload PDF(s) and screen them (multipart) | 201 | 400, 404, 422 |
| GET | `/api/candidates` | Search/filter/sort/paginate results | 200 | 400 |
| GET | `/api/candidates/<id>` | Detail incl. text and score breakdown | 200 | 404 |
| PATCH | `/api/candidates/<id>/review` | Human review status / note | 200 | 400, 404 |
| DELETE | `/api/candidates/<id>` | Delete a candidate's data | 200 | 404 |
| GET | `/api/screenings` | Screening sessions | 200 | - |
| GET | `/api/screenings/<id>` | Session, its candidates, failed files | 200 | 404 |
| GET | `/api/dashboard` | Dashboard statistics | 200 | - |
| GET | `/api/reports/excel` | Excel report (`?session_id=` / `?job_id=`) | 200 | 404 |
| GET | `/api/reports/csv` | CSV report (same filters) | 200 | 404 |
| GET | `/api/reports/summary` | Plain-text summary (same filters) | 200 | 404 |

Uploaded files are never served back; the PDF is deleted after processing unless `KEEP_UPLOADED_FILES=true`.

## Examples (PowerShell; use `curl.exe`, not the `curl` alias)

Create a job (weights 4:2.5:2:1.5 are scaled to 40/25/20/15):
```powershell
curl.exe -X POST http://127.0.0.1:5000/api/jobs -H "Content-Type: application/json" -d '{\"title\":\"Data Analyst\",\"min_experience_years\":1,\"education_requirement\":\"Bachelor''s degree\",\"skills\":[{\"skill\":\"Python\",\"weight\":4},{\"skill\":\"SQL\",\"weight\":2.5},{\"skill\":\"Excel\",\"weight\":2},{\"skill\":\"Communication\",\"weight\":1.5}]}'
```
Upload resumes (optionally `-F session_id=3` to add to an existing session):
```powershell
curl.exe -X POST http://127.0.0.1:5000/api/resumes/upload -F job_id=1 -F "files=@sample_data/resumes/aarav_sharma.pdf" -F "files=@sample_data/resumes/rohan_das.pdf"
```
Response (201; 422 when nothing could be processed):
```json
{"session_id": 1, "summary": {"total": 2, "processed": 2, "failed": 0, "rejected": 0},
 "results": [{"filename": "aarav_sharma.pdf", "status": "processed", "candidate_id": 1, "name": "Aarav Sharma",
              "score": 100.0, "needs_review": false, "warnings": [], "error": null}]}
```
Per-file `status` is `processed`, `processed_with_warnings`, `failed` (readable file, processing error) or `rejected` (failed validation).

List candidates: `GET /api/candidates?q=python&min_score=50&review_status=pending&sort=score&order=desc&page=1&per_page=10`
(filters: `q`, `session_id`, `job_id`, `min_score`, `max_score`, `status`, `review_status`, `needs_review`; sort: `score|name|experience|screened_at|review_status|email`).

Human review:
```powershell
curl.exe -X PATCH http://127.0.0.1:5000/api/candidates/1/review -H "Content-Type: application/json" -d '{\"review_status\":\"shortlisted\",\"note\":\"Call next week\"}'
```
`review_status` is one of `pending`, `shortlisted`, `on_hold`, `not_selected`. Only a person sets it - the system never does.

Reports:
```powershell
curl.exe -o report.xlsx "http://127.0.0.1:5000/api/reports/excel?session_id=1"
curl.exe -o report.csv  "http://127.0.0.1:5000/api/reports/csv?session_id=1"
curl.exe "http://127.0.0.1:5000/api/reports/summary?session_id=1"
```

## Upload validation
Extension must be `.pdf`; MIME type must be `application/pdf` (or generic `application/octet-stream`); size <= `MAX_FILE_MB` (10);
content must start with the `%PDF-` signature and open as a PDF (<= `MAX_PDF_PAGES`, not password protected). Stored names are random
UUIDs - the client file name is only displayed (after `secure_filename`), so path traversal is impossible.
DOCX is intentionally **not** supported (not implemented, so not offered).
