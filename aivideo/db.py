"""Persistent job store using SQLite (upgrade path to Postgres via SQLAlchemy).

Every generated video is stored here so the system can analyse past jobs,
learn from them, and avoid repeating poor choices.

Schema
------
jobs
  id            TEXT PRIMARY KEY    -- 10-char hex uuid
  state         TEXT                -- running | done | error
  status        TEXT                -- human-readable progress message
  format        TEXT                -- deep_dive | brief | critique | debate
  length        TEXT                -- short | default | long
  style         TEXT                -- auto | classic | whiteboard | kawaii
  quality       TEXT                -- draft | standard | cinematic
  engine        TEXT                -- tts engine used
  topic         TEXT                -- lesson topic
  source_hash   TEXT                -- sha256 of source text (for dedup / cache)
  created_at    TEXT                -- ISO-8601
  updated_at    TEXT                -- ISO-8601
  result_json   TEXT                -- full pipeline result as JSON
  traceback     TEXT                -- last error traceback if state=error

video_index
  job_id        TEXT FK jobs.id
  video_path    TEXT                -- absolute path to lesson.mp4
  total_seconds REAL
  scene_count   INTEGER
  quality_score REAL                -- from qa_report if available
  created_at    TEXT
"""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

_LOCK = threading.Lock()
_DB_PATH: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.environ.get(
            "DB_PATH",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "jobs.db")
        )
    return _DB_PATH


def _conn() -> sqlite3.Connection:
    db = get_db_path()
    os.makedirs(os.path.dirname(db), exist_ok=True)
    c = sqlite3.connect(db, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    """Create tables if they do not exist. Safe to call on every startup."""
    with _LOCK, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          TEXT PRIMARY KEY,
            state       TEXT NOT NULL DEFAULT 'running',
            status      TEXT NOT NULL DEFAULT '',
            format      TEXT NOT NULL DEFAULT 'deep_dive',
            length      TEXT NOT NULL DEFAULT 'default',
            style       TEXT NOT NULL DEFAULT 'auto',
            quality     TEXT NOT NULL DEFAULT 'standard',
            engine      TEXT NOT NULL DEFAULT 'kokoro',
            topic       TEXT,
            source_hash TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            result_json TEXT,
            traceback   TEXT
        );

        CREATE TABLE IF NOT EXISTS video_index (
            job_id        TEXT NOT NULL REFERENCES jobs(id),
            video_path    TEXT NOT NULL,
            total_seconds REAL,
            scene_count   INTEGER,
            quality_score REAL,
            created_at    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
        CREATE INDEX IF NOT EXISTS idx_video_job ON video_index(job_id);
        """)


def create_job(job_id: str, **kwargs) -> None:
    """Insert a new job row."""
    now = _now()
    with _LOCK, _conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO jobs
               (id, state, status, format, length, style, quality, engine,
                topic, source_hash, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                kwargs.get("state", "running"),
                kwargs.get("status", "Starting..."),
                kwargs.get("format", "deep_dive"),
                kwargs.get("length", "default"),
                kwargs.get("style",   "auto"),
                kwargs.get("quality", "standard"),
                kwargs.get("engine",  "kokoro"),
                kwargs.get("topic"),
                kwargs.get("source_hash"),
                now, now,
            )
        )


def update_job(job_id: str, **kwargs) -> None:
    """Update any subset of job columns."""
    if not kwargs:
        return
    now = _now()
    # serialise result_json if passed as dict
    if "result_json" in kwargs and isinstance(kwargs["result_json"], dict):
        kwargs["result_json"] = json.dumps(kwargs["result_json"])
    kwargs["updated_at"] = now
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id = ?", vals)


def get_job(job_id: str) -> Optional[dict]:
    """Return job as a dict, or None if not found."""
    with _LOCK, _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("result_json"):
        try:
            d.update(json.loads(d["result_json"]))
        except Exception:
            pass
    return d


def list_jobs(limit: int = 50, offset: int = 0) -> list:
    """List recent jobs, newest first."""
    with _LOCK, _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        if d.get("result_json"):
            try:
                d.update(json.loads(d["result_json"]))
            except Exception:
                pass
        out.append(d)
    return out


def index_video(job_id: str, video_path: str,
                total_seconds: float = 0, scene_count: int = 0,
                quality_score: float = None) -> None:
    """Record a completed video in the video_index for analysis."""
    with _LOCK, _conn() as c:
        c.execute(
            """INSERT INTO video_index
               (job_id, video_path, total_seconds, scene_count, quality_score, created_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, video_path, total_seconds, scene_count, quality_score, _now())
        )


def video_history(limit: int = 20) -> list:
    """Return recent completed videos with their metadata for analysis/learning."""
    with _LOCK, _conn() as c:
        rows = c.execute(
            """SELECT v.*, j.topic, j.format, j.style, j.quality, j.engine
               FROM video_index v JOIN jobs j ON v.job_id = j.id
               ORDER BY v.created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
