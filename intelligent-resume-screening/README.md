# Intelligent Resume Screening and Candidate Shortlisting System
**Using RPA (UiPath), Python (Flask) and OCR (Tesseract)** - academic prototype

A local web application that reads PDF resumes (including scanned ones through OCR), extracts contact details, skills,
education and experience, compares the skills with a job's weighted requirements, and produces a **transparent,
explainable skill-match score** and a ranked Excel report for a **human recruiter** to review.

> **Responsible-use rules built into the design**
> * The score = sum of the weights of the required skills found in the resume. Nothing else.
> * It is *not* a measure of overall quality, personality, intelligence or future performance.
> * Age, gender, photo, caste, religion, disability or other sensitive attributes are never extracted or used.
> * No automatic rejection. Thresholds only **flag** records for manual review; only a person can set "Not selected".
> * Fields that cannot be found are shown as **"Not detected"** - nothing is invented.
> * Everything runs locally. No paid APIs, cloud services or API keys.

## Contents
1. [Features](#features) 2. [Tech stack](#tech-stack) 3. [Windows + VS Code setup](#windows--vs-code-setup)
4. [Using the app](#using-the-app) 5. [Scoring algorithm](#scoring-algorithm) 6. [REST API](#rest-api)
7. [Tests](#tests) 8. [UiPath automation](#uipath-automation) 9. [Selenium demo scraper](#selenium-demo-scraper)
10. [Project structure](#project-structure) 11. [Troubleshooting](#troubleshooting) 12. [Limitations](#limitations)

## Features
* Dashboard: resumes processed, high-score count, manual-review count, average score, recent activity, score-distribution chart (Chart.js).
* Jobs: create/edit/delete, per-skill weights (auto-normalised to 100%), minimum experience, education.
* Upload: multi-file PDF upload with per-file progress/status; validation of extension, MIME type, size and file content.
* Results: search, filters, sorting, pagination; candidate detail page with extracted text and a scoring explanation.
* Human review: status (pending / shortlisted / on hold / not selected) and notes; delete a candidate's data.
* Reports: Excel (3 sheets), CSV, text summary, history of screening sessions with timestamp and the job used.
* OCR for scanned PDFs, with OCR confidence kept and low confidence flagged.
* UiPath automation package + a tested Python batch script, and a Selenium scraper for a local demo job page.
* Fully offline once installed (Bootstrap and Chart.js are bundled in `static/vendor`).

## Tech stack
Flask - PyMuPDF - Tesseract via pytesseract - pandas + openpyxl - SQLite - Bootstrap 5 - Chart.js - Selenium - pytest - UiPath Studio.

## Windows + VS Code setup

### 1. Install Python
Download Python **3.10, 3.11 or 3.12** from https://www.python.org/downloads/windows/ and tick **"Add python.exe to PATH"**. Verify:
```powershell
python --version
```

### 2. Install Tesseract OCR (needed only for scanned PDFs)
1. Download the Windows installer from https://github.com/UB-Mannheim/tesseract/wiki and install (default path
   `C:\Program Files\Tesseract-OCR`). Keep the "English" language data selected.
2. The app finds it automatically in the default folder or on `PATH`. If you installed elsewhere, set the path in `.env` (step 4).
3. Verify: `& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version`

### 3. Open the project in VS Code
Unzip the project, then in VS Code: **File -> Open Folder...** -> `intelligent-resume-screening`. Open the terminal with **Ctrl + `** (PowerShell).
Install the VS Code *Python* extension if prompted.

### 4. Create the virtual environment, install packages, configure
**Fast way (recommended):** double-click `scripts\setup_windows.bat` (it does everything below).

**Manual way (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env               # edit TESSERACT_CMD if needed
```
In VS Code press **Ctrl+Shift+P -> "Python: Select Interpreter" -> choose `.\venv\Scripts\python.exe`**.

### 5. Initialise the database (with the fictional sample job)
```powershell
python database\seed.py
```
Use `python database\seed.py --reset` to wipe and recreate it.

### 6. Generate fictional sample resumes
```powershell
python sample_data\GenerateSampleResumes.py
```
Creates `sample_data\resumes\` with 6 text PDFs, 1 scanned PDF (tests OCR) and 1 invalid file (tests validation). All data is made up.

### 7. Start the application
```powershell
python app.py
```
or double-click `scripts\run_app.bat` (also opens the browser).

### 8. Open the website
http://127.0.0.1:5000 - the health check is at http://127.0.0.1:5000/api/health (shows whether Tesseract was found).

## Using the app
1. **Jobs -> New job** (or use the seeded "Junior Data Analyst"). Enter title, description, skills and weights (e.g. Python 40, SQL 25, Excel 20, Communication 15). Weights are scaled to total 100%.
2. **Upload**: choose the job, drop PDFs from `sample_data\resumes`, click **Upload & process**. You see progress and status per file (the invalid file is rejected with a reason).
3. **Candidates**: search, filter, sort; open a candidate for the scoring explanation, evidence, extracted text, processing log; set a review status and note.
4. **Reports**: download Excel / CSV / summary for a session or for all results.
   Excel files are also saved in `outputs\`.
5. **Dashboard** updates automatically.

Expected sample result against "Junior Data Analyst": Aarav Sharma 100%, Vikram Singh (scanned, via OCR) 100%, Karan Mehta 85%, Meera Iyer 60%, Rohan Das 60%, Sneha Rao 35%, Priya Nair 0% (Java/JavaScript profile - no false match on "java"/"js"), plus one rejected invalid file.

## Scoring algorithm
```
Skill Match Score = sum( weight(skill) for each required skill found in the resume )   (weights total 100)
```
* Weights are validated (positive numbers, no empty or duplicate skills) and scaled to exactly 100 (equal split if none are given).
* Matching is deterministic: lower-cased text, **whole-word regular expressions**, so `java` never matches `javascript`, `sql` never matches inside other words, and `C++`/`C#`/`Node.js` work.
* Aliases live in `data/skills_dictionary.json` (edit freely): PostgreSQL/MySQL -> SQL, JS -> JavaScript, "Microsoft Excel" -> Excel.
* *Context aliases*: "py" counts as Python **only** if words like pandas/numpy/flask also appear.
* Each skill shows its evidence (matched term and a text snippet). Missing skills are labelled "not found / unconfirmed" because the resume may phrase them differently.
* Experience and education requirements are checked and displayed (met / not met / unconfirmed) but **do not change the score**.
* `REVIEW_THRESHOLD` (default 50) and `HIGH_MATCH_THRESHOLD` (default 70) only drive dashboard counts and review flags.

## REST API
Full reference and PowerShell examples: [`docs/API.md`](docs/API.md). Endpoints include `GET /api/health`, `GET|POST /api/jobs`, `GET /api/jobs/<id>`,
`POST /api/resumes/upload`, `GET /api/candidates`, `GET /api/candidates/<id>`, `PATCH /api/candidates/<id>/review`,
`GET /api/screenings`, `GET /api/screenings/<id>`, `GET /api/reports/excel|csv|summary`.

## Tests
```powershell
python -m pytest -v        # or scripts\run_tests.bat
```
61 tests cover: skill matching (false positives, aliases, weights), parsing/OCR, API validation and security (bad files, path traversal, escaping),
filtering/pagination, review flow, Excel/CSV/summary reports, formula-injection protection, and the demo-page parser. The OCR test is skipped automatically if Tesseract is missing.

## UiPath automation
Folder: [`automation/`](automation/README.md). It contains a full build guide ([`workflow_design.md`](automation/workflow_design.md)),
[`variables.md`](automation/variables.md), [`selectors.md`](automation/selectors.md) and Mermaid flowcharts ([`automation/flows`](automation/flows/README.md)).

Quick summary of the robot: verify/start Flask -> read PDFs from an input folder -> pick the job -> run `scripts\process_resumes.py` (Start Process) ->
record success/failure -> download the Excel report to the output folder -> log total / successful / failed, with retries and Try Catch.

Test the Python side first - this is exactly what UiPath runs:
```powershell
python scripts\process_resumes.py --input-folder sample_data\resumes --output-folder outputs --job-id 1 --start-server
```
Exit codes: `0` all OK, `1` some files failed (expected 1 with the sample set), `2` fatal. The last line printed is a JSON summary.

> I did not include a `.xaml` project because a hand-written one would not reliably open in your Studio version. The guide lists every activity, property, argument and expression instead.

## Selenium demo scraper
```powershell
python scraper\scrape_job.py                # dry run: opens the local demo page in headless Chrome and prints the job
python scraper\scrape_job.py --save         # also saves it through the API (the Flask app must be running)
python scraper\scrape_job.py --engine html  # no browser needed
```
Needs Google Chrome (Selenium 4 downloads the matching driver on first use - that one-time step needs internet; the page itself is local).
It uses explicit waits and `data-testid` selectors and only reads the page bundled with this project.

## Project structure
```
app.py  config.py  requirements.txt  .env.example  pytest.ini
database/   schema.sql  db.py  queries.py  seed.py
services/   resume_parser.py  ocr_service.py  contact_extractor.py  experience_extractor.py
            skill_matcher.py  pipeline.py  report_service.py
routes/     jobs.py  resumes.py  candidates.py  reports.py  pages.py
templates/  base, index, jobs, job_form, upload, candidates, candidate_detail, screenings, error
static/     css/style.css  js/*.js  vendor/ (Bootstrap, Chart.js)
data/       skills_dictionary.json
scraper/    demo_job_page.html  scrape_job.py
scripts/    setup_windows.bat  run_app.bat  run_tests.bat  run_rpa_batch.bat  process_resumes.py
automation/ UiPath guide, variables, selectors, flows/*.mmd
sample_data/  job_description.json  GenerateSampleResumes.py
tests/      pytest suite      docs/API.md
uploads/ outputs/  (runtime folders)
```

## Troubleshooting
| Problem | Fix |
|---------|-----|
| **`python` is not recognised / Python not found** | Reinstall Python and tick *Add python.exe to PATH*, or run `py -3 -m venv venv`. Close and reopen the terminal afterwards. |
| **PowerShell: running scripts is disabled** | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `venv\Scripts\activate.bat` in Command Prompt. |
| **`pip install` errors** | Run `python -m pip install --upgrade pip` first. Use Python 3.10-3.12 (very new versions may lack wheels). Behind a proxy/firewall? `pip install -r requirements.txt --proxy http://user:pass@host:port`. If PyMuPDF fails, try `pip install --upgrade PyMuPDF`. |
| **Tesseract not found / "OCR unavailable" warning** | Install Tesseract (step 2). Then set in `.env`: `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` and restart. Check `/api/health` -> `"ocr_available": true`. Text PDFs work without it. |
| **`ModuleNotFoundError: No module named 'flask'` (or fitz, pandas...)** | The virtual environment is not active or the wrong interpreter is selected. Run `.\venv\Scripts\Activate.ps1` and `pip install -r requirements.txt`; select the venv interpreter in VS Code. |
| **SQLite errors (`database is locked`, `no such table`, `unable to open database file`)** | Close other programs using the file; run `python database\seed.py` to create tables; make sure the project is in a normal writable folder (not Program Files). To start fresh: `python database\seed.py --reset`. |
| **PDF extraction failures** | The message appears on the candidate/failed list: *not a real PDF* (renamed file), *password protected* (remove the password), *no text and OCR unavailable* (install Tesseract), or *too many pages* (limit 30). Very low OCR confidence -> use a cleaner scan (200-300 dpi). |
| **Port 5000 already in use** | `netstat -ano \| findstr :5000` then `taskkill /PID <pid> /F`, or set `PORT=5001` in `.env` and open http://127.0.0.1:5001 (update `BaseUrl` for UiPath/scripts). |
| **UiPath: Start Process does nothing / exit code is not 0** | Use the *full path* to `venv\Scripts\python.exe`, quote paths with spaces, set WorkingDirectory to the project root, and read `outputs\process_resumes.log` and `last_run_summary.json`. Exit code 2 means the server was unreachable - check the app/port or add `--start-server`. |
| **UiPath: Python Scope / version errors** | Use the Start Process route instead; if you need Python Scope, point it to the venv's `Scripts` folder and match the Python version and 64-bit target. |
| **UiPath: selector not found** | Use the `data-testid` selectors in `automation/selectors.md`; make sure the page is open and the browser extension is installed. |
| **Selenium: "session not created"/driver errors** | Update Chrome; the first run needs internet so Selenium Manager can fetch the driver; or use `--engine html`. |
| **Upload shows "Network error"** | The Flask server is not running - start it with `scripts\run_app.bat`. |

## Limitations
* Skill detection is dictionary/keyword based: it will miss synonyms that are not in the dictionary and cannot judge depth of skill. Edit `data/skills_dictionary.json` to extend it.
* Name, education and experience extraction are heuristics - they can be wrong or missing, hence "Not detected" and mandatory human review.
* OCR accuracy depends on scan quality; English only by default.
* PDF only. DOCX is not supported (deliberately - it was not implemented/tested).
* Single-user local prototype: no login, no CSRF protection, no encryption at rest. Do not expose it to a network or use real applicants' data without proper consent, security and legal review.
* Resumes are processed in the web request (fine for dozens of files, not thousands).
* Uploaded PDFs are deleted after processing; only extracted text and fields are stored. Use *Delete data* on a candidate page, or delete `database\screening.db`, to erase stored data.

## Verification performed while building
Syntax/imports checked; 61 automated tests pass on Python 3.12 (Linux sandbox) including real Tesseract OCR; the live server was exercised end to end with the batch script (7 resumes processed, invalid file rejected, Excel/CSV/summary downloaded and opened). The Selenium/Chrome path, the Windows `.bat` files and the UiPath workflow could **not** be run in the build environment - they follow documented behaviour but please report anything that differs on your machine.
