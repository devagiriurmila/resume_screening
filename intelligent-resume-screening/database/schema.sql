PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT NOT NULL DEFAULT '',
    min_experience_years REAL NOT NULL DEFAULT 0 CHECK (min_experience_years >= 0),
    education_requirement TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill TEXT NOT NULL CHECK (length(trim(skill)) > 0),
    weight REAL NOT NULL CHECK (weight > 0 AND weight <= 100),
    UNIQUE (job_id, skill)
);

-- A session = one batch of resumes screened against one job. The job is snapshotted
-- so later edits to the job never change historical results.
CREATE TABLE IF NOT EXISTS screening_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    job_title TEXT NOT NULL,
    job_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES screening_sessions(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_filename TEXT,
    sha256 TEXT NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size >= 0),
    page_count INTEGER,
    extraction_method TEXT CHECK (extraction_method IN ('text', 'ocr', 'mixed', 'none')),
    ocr_confidence REAL,
    extracted_text TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    processing_status TEXT NOT NULL DEFAULT 'processing'
        CHECK (processing_status IN ('processing', 'processed', 'processed_with_warnings', 'failed')),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (session_id, sha256)
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL UNIQUE REFERENCES resumes(id) ON DELETE CASCADE,
    name TEXT,
    email TEXT,
    phone TEXT,
    education TEXT,
    experience_years REAL,
    experience_method TEXT,
    skills_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS screening_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES screening_sessions(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    matched_json TEXT NOT NULL DEFAULT '[]',
    missing_json TEXT NOT NULL DEFAULT '[]',
    breakdown_json TEXT NOT NULL DEFAULT '[]',
    requirement_checks_json TEXT NOT NULL DEFAULT '{}',
    needs_review INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0, 1)),
    review_reasons_json TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'shortlisted', 'on_hold', 'not_selected')),
    reviewer_note TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES screening_sessions(id) ON DELETE CASCADE,
    resume_id INTEGER REFERENCES resumes(id) ON DELETE CASCADE,
    level TEXT NOT NULL CHECK (level IN ('INFO', 'WARNING', 'ERROR')),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_job_skills_job ON job_skills(job_id);
CREATE INDEX IF NOT EXISTS idx_resumes_session ON resumes(session_id);
CREATE INDEX IF NOT EXISTS idx_results_session ON screening_results(session_id);
CREATE INDEX IF NOT EXISTS idx_results_score ON screening_results(score);
CREATE INDEX IF NOT EXISTS idx_logs_resume ON processing_logs(resume_id);
