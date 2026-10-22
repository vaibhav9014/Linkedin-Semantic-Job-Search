"""SQLite persistence for fetched listings and server-side OAuth sessions."""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings
from models.schemas import Job


class JobStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS oauth_sessions (
                    session_id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    scopes TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS jsearch_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    cached_at REAL NOT NULL
                )
            """)

    def save_jobs(self, jobs: list[Job]) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO jobs (job_id, job_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    job_json = excluded.job_json,
                    updated_at = excluded.updated_at
                """,
                [
                    (job.job_id, job.model_dump_json(), timestamp)
                    for job in jobs
                ],
            )

    def count_jobs(self) -> int:
        with self.connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def get_cached_search(self, cache_key: str, ttl_seconds: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT response_json, cached_at FROM jsearch_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            if time.time() - row["cached_at"] >= ttl_seconds:
                connection.execute(
                    "DELETE FROM jsearch_cache WHERE cache_key = ?",
                    (cache_key,),
                )
                return None
        return json.loads(row["response_json"])

    def cache_search(self, cache_key: str, response: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO jsearch_cache (cache_key, response_json, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    cached_at = excluded.cached_at
                """,
                (cache_key, json.dumps(response), time.time()),
            )

    def save_session(
        self,
        session_id: str,
        member_id: str,
        profile: dict,
        access_token: str,
        expires_at: float,
        scopes: list[str],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO oauth_sessions
                    (session_id, member_id, profile_json, access_token, expires_at, scopes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    member_id = excluded.member_id,
                    profile_json = excluded.profile_json,
                    access_token = excluded.access_token,
                    expires_at = excluded.expires_at,
                    scopes = excluded.scopes,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    member_id,
                    json.dumps(profile),
                    access_token,
                    expires_at,
                    " ".join(scopes),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_session(self, session_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM oauth_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "member_id": row["member_id"],
            "profile": json.loads(row["profile_json"]),
            "access_token": row["access_token"],
            "expires_at": row["expires_at"],
            "scopes": row["scopes"].split(),
        }

job_store = JobStore(settings.jobs_db_path)
