from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def _db_path() -> Path:
    return Path(settings.sqlite_db_path)


def init_db() -> None:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS provisioning_requests (
                request_id TEXT PRIMARY KEY,
                requested_by TEXT NOT NULL,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                gitlab_project_id TEXT NOT NULL,
                gitlab_pipeline_id INTEGER,
                gitlab_pipeline_url TEXT,
                request_payload TEXT NOT NULL,
                terraform_payload TEXT NOT NULL,
                pipeline_request TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


@contextmanager
def get_connection():
    connection = sqlite3.connect(_db_path())
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
