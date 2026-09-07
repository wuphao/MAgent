CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assets (
    project_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    media_type TEXT NOT NULL,
    source_namespace TEXT NOT NULL,
    uri TEXT NOT NULL,
    available_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (project_id, asset_id, revision),
    UNIQUE (project_id, content_hash)
);
