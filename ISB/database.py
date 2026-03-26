"""
database.py
===========
Handles all database operations:
- Table creation
- Insert / update / delete
- Indexed search queries
- Optimization and deduplication
- Statistics aggregation
"""

import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = "text_processor.db"

# Thread-local storage so each thread gets its own connection
_local = threading.local()


@contextmanager
def get_connection():
    """
    Provide a transactional scope around a series of operations.
    Uses thread-local connections so parallel workers don't share state.
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row          # dict-like rows
        _local.conn.execute("PRAGMA journal_mode=WAL")  # allow concurrent reads
        _local.conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield _local.conn
        _local.conn.commit()
    except Exception:
        _local.conn.rollback()
        raise


# ─────────────────────────────────────────────────────────────────────────────
# INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables and indexes on first run."""
    with get_connection() as conn:
        conn.executescript("""
            -- Main storage for every processed chunk
            CREATE TABLE IF NOT EXISTS text_chunks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name        TEXT    NOT NULL,
                chunk_index      INTEGER NOT NULL,
                chunk_text       TEXT    NOT NULL,
                sentiment_score  REAL    DEFAULT 0,
                sentiment_label  TEXT    DEFAULT 'neutral',
                positive_words   TEXT,          -- JSON list
                negative_words   TEXT,          -- JSON list
                tags             TEXT,          -- JSON list
                pattern_matches  TEXT,          -- JSON list
                word_count       INTEGER DEFAULT 0,
                char_count       INTEGER DEFAULT 0,
                processed_at     TEXT    NOT NULL,
                batch_id         TEXT
            );

            -- One row per uploaded file / batch
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id         TEXT    UNIQUE NOT NULL,
                file_name        TEXT    NOT NULL,
                file_size        INTEGER,
                total_chunks     INTEGER DEFAULT 0,
                completed_chunks INTEGER DEFAULT 0,
                status           TEXT    DEFAULT 'pending',
                started_at       TEXT,
                completed_at     TEXT,
                error_message    TEXT
            );

            -- Indexes for fast search
            CREATE INDEX IF NOT EXISTS idx_score
                ON text_chunks(sentiment_score);
            CREATE INDEX IF NOT EXISTS idx_label
                ON text_chunks(sentiment_label);
            CREATE INDEX IF NOT EXISTS idx_batch
                ON text_chunks(batch_id);
            CREATE INDEX IF NOT EXISTS idx_file
                ON text_chunks(file_name);
            CREATE INDEX IF NOT EXISTS idx_processed_at
                ON text_chunks(processed_at);
        """)
    logger.info("Database initialised at %s", DB_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# JOB MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_job(batch_id: str, file_name: str, file_size: int, total_chunks: int):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO processing_jobs
               (batch_id, file_name, file_size, total_chunks, status, started_at)
               VALUES (?, ?, ?, ?, 'processing', ?)""",
            (batch_id, file_name, file_size, total_chunks,
             datetime.utcnow().isoformat())
        )


def update_job_progress(batch_id: str, completed: int):
    with get_connection() as conn:
        conn.execute(
            """UPDATE processing_jobs
               SET completed_chunks = ?
               WHERE batch_id = ?""",
            (completed, batch_id)
        )


def finish_job(batch_id: str, status: str = "completed", error: str = None):
    with get_connection() as conn:
        conn.execute(
            """UPDATE processing_jobs
               SET status = ?, completed_at = ?, error_message = ?
               WHERE batch_id = ?""",
            (status, datetime.utcnow().isoformat(), error, batch_id)
        )


def get_job(batch_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM processing_jobs WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# CHUNK STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def insert_chunk(data: dict):
    """Insert a single processed chunk record."""
    import json
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO text_chunks
               (file_name, chunk_index, chunk_text, sentiment_score,
                sentiment_label, positive_words, negative_words,
                tags, pattern_matches, word_count, char_count,
                processed_at, batch_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("file_name"),
                data.get("chunk_index"),
                data.get("chunk_text"),
                data.get("sentiment_score", 0),
                data.get("sentiment_label", "neutral"),
                json.dumps(data.get("positive_words", [])),
                json.dumps(data.get("negative_words", [])),
                json.dumps(data.get("tags", [])),
                json.dumps(data.get("pattern_matches", [])),
                data.get("word_count", 0),
                data.get("char_count", 0),
                datetime.utcnow().isoformat(),
                data.get("batch_id"),
            )
        )


def bulk_insert_chunks(records: list):
    """Fast bulk insert using executemany."""
    import json
    rows = [
        (
            r.get("file_name"), r.get("chunk_index"), r.get("chunk_text"),
            r.get("sentiment_score", 0), r.get("sentiment_label", "neutral"),
            json.dumps(r.get("positive_words", [])),
            json.dumps(r.get("negative_words", [])),
            json.dumps(r.get("tags", [])),
            json.dumps(r.get("pattern_matches", [])),
            r.get("word_count", 0), r.get("char_count", 0),
            datetime.utcnow().isoformat(), r.get("batch_id"),
        )
        for r in records
    ]
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO text_chunks
               (file_name, chunk_index, chunk_text, sentiment_score,
                sentiment_label, positive_words, negative_words,
                tags, pattern_matches, word_count, char_count,
                processed_at, batch_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows
        )


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH & RETRIEVAL
# ─────────────────────────────────────────────────────────────────────────────

def search_chunks(
    keyword: str = None,
    min_score: float = None,
    max_score: float = None,
    label: str = None,
    batch_id: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Flexible search with pagination.
    Returns { total, page, page_size, results[] }
    """
    import json

    clauses, params = [], []

    if keyword:
        clauses.append("chunk_text LIKE ?")
        params.append(f"%{keyword}%")
    if min_score is not None:
        clauses.append("sentiment_score >= ?")
        params.append(min_score)
    if max_score is not None:
        clauses.append("sentiment_score <= ?")
        params.append(max_score)
    if label:
        clauses.append("sentiment_label = ?")
        params.append(label)
    if batch_id:
        clauses.append("batch_id = ?")
        params.append(batch_id)
    if date_from:
        clauses.append("processed_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("processed_at <= ?")
        params.append(date_to)

    where  = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    offset = (page - 1) * page_size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM text_chunks {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT * FROM text_chunks {where}
                ORDER BY id DESC LIMIT ? OFFSET ?""",
            params + [page_size, offset]
        ).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        for field in ("positive_words", "negative_words", "tags", "pattern_matches"):
            try:
                r[field] = json.loads(r[field]) if r[field] else []
            except Exception:
                r[field] = []
        results.append(r)

    return {"total": total, "page": page, "page_size": page_size, "results": results}


def get_all_chunks_for_export(batch_id: str = None) -> list:
    """Return all chunks (optionally filtered by batch) for CSV export."""
    import json
    query  = "SELECT * FROM text_chunks"
    params = []
    if batch_id:
        query += " WHERE batch_id = ?"
        params.append(batch_id)
    query += " ORDER BY id ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        for field in ("positive_words", "negative_words", "tags", "pattern_matches"):
            try:
                r[field] = ", ".join(json.loads(r[field])) if r[field] else ""
            except Exception:
                r[field] = ""
        results.append(r)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def get_statistics(batch_id: str = None) -> dict:
    where  = "WHERE batch_id = ?" if batch_id else ""
    params = [batch_id] if batch_id else []

    with get_connection() as conn:
        row = conn.execute(
            f"""SELECT
                    COUNT(*)                        AS total_chunks,
                    AVG(sentiment_score)            AS avg_score,
                    MAX(sentiment_score)            AS max_score,
                    MIN(sentiment_score)            AS min_score,
                    SUM(word_count)                 AS total_words,
                    SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) AS positive_count,
                    SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) AS negative_count,
                    SUM(CASE WHEN sentiment_label='neutral'  THEN 1 ELSE 0 END) AS neutral_count
                FROM text_chunks {where}""",
            params
        ).fetchone()

    return dict(row) if row else {}


# ─────────────────────────────────────────────────────────────────────────────
# OPTIMISATION (Text Storage Improver – Module 4)
# ─────────────────────────────────────────────────────────────────────────────

def optimize_database():
    """
    Remove duplicates, run VACUUM, and ensure all indexes exist.

    FIX: VACUUM cannot run inside a transaction in SQLite.
    We open a separate autocommit connection for VACUUM and ANALYZE.
    """
    # Step 1: Remove duplicate chunks (runs inside normal transaction)
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM text_chunks
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM text_chunks
                GROUP BY file_name, chunk_text
            )
        """)

    # Step 2: VACUUM + ANALYZE must run outside any transaction (autocommit)
    vacuum_conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        vacuum_conn.execute("VACUUM")
        vacuum_conn.execute("ANALYZE")
    finally:
        vacuum_conn.close()

    logger.info("Database optimised: duplicates removed, VACUUM + ANALYZE complete.")


def archive_old_chunks(days: int = 30):
    """Move chunks older than `days` to an archive table."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS text_chunks_archive
            AS SELECT * FROM text_chunks WHERE 0
        """)
        cutoff = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff -= timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        conn.execute("""
            INSERT INTO text_chunks_archive
            SELECT * FROM text_chunks WHERE processed_at < ?
        """, (cutoff_str,))

        conn.execute(
            "DELETE FROM text_chunks WHERE processed_at < ?", (cutoff_str,)
        )
    logger.info("Archived chunks older than %d days.", days)