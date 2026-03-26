"""
parallel_processor.py
=====================
Module 1 (part B) + Module 2 – Parallel Execution Engine
----------------------------------------------------------
Distributes chunks across workers using:
  • concurrent.futures.ThreadPoolExecutor   (I/O-bound stages)
  • concurrent.futures.ProcessPoolExecutor  (CPU-bound scoring)

Automatically selects optimal worker count based on CPU cores and chunk count.
Reports progress back via a shared dict so the API can poll /status.
"""

import os
import math
import uuid
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict

from file_loader import load_and_chunk
from sentiment_engine import analyse_chunk, SentimentResult
import database as db

logger = logging.getLogger(__name__)

# ── Global progress tracker (batch_id → progress dict) ───────────────────────
_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def start_processing(
    file_path: str,
    file_name: str,
    file_size: int,
    num_workers: int = None,
    use_multiprocessing: bool = False,
) -> str:
    """
    Kick off parallel processing in a background thread.
    Returns batch_id immediately so the caller can poll /status.

    Parameters
    ----------
    file_path          : absolute path to the uploaded file
    file_name          : original filename (used for ext detection + DB storage)
    file_size          : file size in bytes
    num_workers        : override auto worker count
    use_multiprocessing: True → ProcessPoolExecutor (CPU-bound)
                         False → ThreadPoolExecutor (default, I/O-bound)
    """
    batch_id = str(uuid.uuid4())

    with _progress_lock:
        _progress[batch_id] = {
            "status":           "loading",
            "total_chunks":     0,
            "completed_chunks": 0,
            "percent":          0,
            "error":            None,
        }

    # Spin up a background thread so the HTTP response returns instantly
    t = threading.Thread(
        target=_run_pipeline,
        args=(batch_id, file_path, file_name, file_size,
              num_workers, use_multiprocessing),
        daemon=True,
    )
    t.start()

    return batch_id


def get_progress(batch_id: str) -> dict:
    with _progress_lock:
        return dict(_progress.get(batch_id, {"error": "batch not found"}))


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline(
    batch_id: str,
    file_path: str,
    file_name: str,
    file_size: int,
    num_workers: int,
    use_multiprocessing: bool,
):
    try:
        # ── STAGE 1: Load + Chunk ─────────────────────────────────────────────
        _update_progress(batch_id, status="loading")
        logger.info("[%s] Loading file '%s'", batch_id, file_name)

        chunks: list[list[str]] = load_and_chunk(file_path, file_name)
        total = len(chunks)

        if total == 0:
            _update_progress(batch_id, status="error",
                             error="File produced 0 chunks. Check file content.")
            db.finish_job(batch_id, status="error",
                          error="File produced 0 chunks")
            return

        # ── Decide worker count ───────────────────────────────────────────────
        if num_workers is None:
            num_workers = _optimal_workers(total, use_multiprocessing)

        db.create_job(batch_id, file_name, file_size, total)
        _update_progress(batch_id, status="processing", total_chunks=total)
        logger.info("[%s] %d chunks, %d workers, multiprocessing=%s",
                    batch_id, total, num_workers, use_multiprocessing)

        # ── STAGE 2: Parallel Sentiment Scoring ───────────────────────────────
        results: list[dict] = _parallel_score(
            batch_id, chunks, file_name, num_workers, use_multiprocessing
        )

        # ── STAGE 3: Bulk insert into DB ──────────────────────────────────────
        _update_progress(batch_id, status="saving")
        db.bulk_insert_chunks(results)
        db.update_job_progress(batch_id, total)
        db.finish_job(batch_id, status="completed")

        _update_progress(batch_id, status="completed",
                         completed_chunks=total, percent=100)
        logger.info("[%s] Pipeline complete. %d records saved.", batch_id, total)

    except Exception as exc:
        logger.exception("[%s] Pipeline failed: %s", batch_id, exc)
        _update_progress(batch_id, status="error", error=str(exc))
        db.finish_job(batch_id, status="error", error=str(exc))


def _parallel_score(
    batch_id: str,
    chunks: list[list[str]],
    file_name: str,
    num_workers: int,
    use_multiprocessing: bool,
) -> list[dict]:
    """
    Score every chunk in parallel.

    Uses ThreadPoolExecutor by default (safe for Flask / SQLite).
    ProcessPoolExecutor can be enabled for purely CPU-heavy workloads
    on machines with multiple physical cores.
    """
    total   = len(chunks)
    results = [None] * total   # pre-allocate to preserve order

    Executor = ProcessPoolExecutor if use_multiprocessing else ThreadPoolExecutor

    with Executor(max_workers=num_workers) as executor:
        # Submit all tasks
        future_to_idx = {
            executor.submit(_score_chunk, chunk_lines, i): i
            for i, chunk_lines in enumerate(chunks)
        }

        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                chunk_text, sentiment = future.result()
                results[idx] = _build_record(
                    batch_id, file_name, idx, chunk_text, sentiment
                )
            except Exception as exc:
                logger.warning("[%s] Chunk %d failed: %s", batch_id, idx, exc)
                results[idx] = _build_error_record(batch_id, file_name, idx)

            completed += 1
            pct = math.floor(completed / total * 100)
            _update_progress(batch_id, completed_chunks=completed,
                             percent=pct, status="processing")
            db.update_job_progress(batch_id, completed)

    return [r for r in results if r is not None]


# ─────────────────────────────────────────────────────────────────────────────
# WORKER FUNCTION  (must be top-level for multiprocessing pickling)
# ─────────────────────────────────────────────────────────────────────────────

def _score_chunk(chunk_lines: list[str], index: int):
    """
    Called inside a worker thread/process.
    Joins lines into a single string then runs sentiment analysis.
    """
    chunk_text = " ".join(chunk_lines)
    sentiment  = analyse_chunk(chunk_text)
    return chunk_text, sentiment


# ─────────────────────────────────────────────────────────────────────────────
# RECORD BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_record(batch_id, file_name, idx, chunk_text, sentiment: SentimentResult) -> dict:
    return {
        "batch_id":        batch_id,
        "file_name":       file_name,
        "chunk_index":     idx,
        "chunk_text":      chunk_text[:5000],  # guard against huge chunks in DB
        "sentiment_score": round(sentiment.sentiment_score, 4),
        "sentiment_label": sentiment.sentiment_label,
        "positive_words":  sentiment.positive_words,
        "negative_words":  sentiment.negative_words,
        "tags":            sentiment.tags,
        "pattern_matches": sentiment.pattern_matches,
        "word_count":      sentiment.word_count,
        "char_count":      sentiment.char_count,
    }


def _build_error_record(batch_id, file_name, idx) -> dict:
    return {
        "batch_id":        batch_id,
        "file_name":       file_name,
        "chunk_index":     idx,
        "chunk_text":      "[processing error]",
        "sentiment_score": 0.0,
        "sentiment_label": "neutral",
        "positive_words":  [],
        "negative_words":  [],
        "tags":            ["error"],
        "pattern_matches": [],
        "word_count":      0,
        "char_count":      0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _optimal_workers(total_chunks: int, use_multiprocessing: bool) -> int:
    """
    Heuristic worker count:
      - Never more than total_chunks (no point having idle workers)
      - For threads:   cap at 2× CPU count (I/O overlap)
      - For processes: cap at CPU count    (true parallelism)
    """
    cpu_count = os.cpu_count() or 2
    if use_multiprocessing:
        cap = cpu_count
    else:
        cap = min(cpu_count * 2, 32)   # 32 threads max
    return min(total_chunks, cap)


def _update_progress(batch_id: str, **kwargs):
    with _progress_lock:
        if batch_id in _progress:
            _progress[batch_id].update(kwargs)