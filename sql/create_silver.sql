PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_label TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS neighbourhoods (
    neighbourhood_id INTEGER PRIMARY KEY,
    neighbourhood_name TEXT NOT NULL UNIQUE,
    neighbourhood_group TEXT
);

CREATE TABLE IF NOT EXISTS neighbourhood_geometries (
    neighbourhood_id INTEGER PRIMARY KEY,
    geometry_type TEXT NOT NULL,
    geometry_json TEXT NOT NULL,
    source_file TEXT NOT NULL,
    FOREIGN KEY (neighbourhood_id)
        REFERENCES neighbourhoods(neighbourhood_id),
    CHECK (json_valid(geometry_json))
);

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id INTEGER PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    source_rows INTEGER,
    loaded_rows INTEGER,
    error_message TEXT
);
