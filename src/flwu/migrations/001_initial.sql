PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    mode          TEXT NOT NULL CHECK(mode IN ('fixture','production')),
    window_start  TEXT NOT NULL,
    window_end    TEXT NOT NULL,
    status        TEXT NOT NULL CHECK(status IN ('running','success_changes','success_no_changes','incomplete','failed','cancelled','budget_exceeded')),
    created_at    TEXT NOT NULL,
    finished_at   TEXT,
    error_code    TEXT
);

CREATE TABLE IF NOT EXISTS source_attempts (
    attempt_id   TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    source_id    TEXT NOT NULL,
    status       TEXT NOT NULL CHECK(status IN ('running','complete','incomplete','failed','cancelled','budget_exceeded')),
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    coverage_json TEXT NOT NULL,
    error_code   TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    document_id  TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL,
    document_key TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    UNIQUE(source_id, document_key)
);

CREATE TABLE IF NOT EXISTS revisions (
    revision_id   TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(document_id),
    content_sha256 TEXT NOT NULL,
    record_json   TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    UNIQUE(document_id, content_sha256)
);

CREATE TABLE IF NOT EXISTS observations (
    attempt_id  TEXT NOT NULL REFERENCES source_attempts(attempt_id),
    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    observed_at TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY(attempt_id, revision_id)
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    analysis_id  TEXT PRIMARY KEY,
    revision_id  TEXT NOT NULL REFERENCES revisions(revision_id),
    profile_id   TEXT NOT NULL,
    status       TEXT NOT NULL CHECK(status IN ('pending','running','done','needs_review','failed')),
    attempts     INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
    lease_until  TEXT,
    claim_token  TEXT,
    result_json  TEXT,
    error_code   TEXT,
    UNIQUE(revision_id, profile_id)
);

CREATE TABLE IF NOT EXISTS analysis_job_reviews (
    review_id         TEXT PRIMARY KEY,
    analysis_id      TEXT NOT NULL REFERENCES analysis_jobs(analysis_id),
    reviewed_at      TEXT NOT NULL,
    reviewer         TEXT NOT NULL,
    authority_reference TEXT NOT NULL,
    reason           TEXT NOT NULL,
    prior_attempts   INTEGER NOT NULL CHECK(prior_attempts >= 0),
    prior_result_json TEXT,
    prior_error_code TEXT
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    snapshot_id   TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL,
    attempt_id    TEXT NOT NULL UNIQUE REFERENCES source_attempts(attempt_id),
    watermark_utc TEXT NOT NULL,
    revision_ids_json TEXT NOT NULL,
    coverage_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_checkpoints (
    source_id   TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
    watermark_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_attempts_run_id ON source_attempts(run_id);
CREATE INDEX IF NOT EXISTS idx_revisions_document_id ON revisions(document_id);
CREATE INDEX IF NOT EXISTS idx_observations_revision_id ON observations(revision_id);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_revision_id ON analysis_jobs(revision_id);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status ON analysis_jobs(status);
