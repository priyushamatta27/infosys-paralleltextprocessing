"""
file_loader.py
==============
Module 1 (part A) – Text Breaker and Loader
--------------------------------------------
Supports ANY text-based file format:
  .txt  .csv  .tsv  .json  .xml  .html  .pdf  .docx  .xlsx  .log  .md

Handles files of ANY size via streaming / lazy reading.
Performs DYNAMIC CHUNKING based on content type and row/line count.
"""

import os
import io
import csv
import json
import logging
import re
from pathlib import Path

try:
    import chardet
    _HAS_CHARDET = True
except ImportError:
    _HAS_CHARDET = False

logger = logging.getLogger(__name__)

# ── Supported extensions ──────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {
    ".txt", ".csv", ".tsv", ".json", ".xml", ".html",
    ".pdf", ".docx", ".xlsx", ".log", ".md", ".text"
}

# ── Dynamic chunk-size boundaries ────────────────────────────────────────────
# The chunk size (in lines/rows) scales with file size so that
# very large files still get parallel distribution without creating
# millions of tiny tasks.
CHUNK_THRESHOLDS = [
    (0,        500,    10),    # tiny   files  → 10 lines/chunk
    (500,      5_000,  50),    # small  files  → 50 lines/chunk
    (5_000,    50_000, 200),   # medium files  → 200 lines/chunk
    (50_000,   500_000, 500),  # large  files  → 500 lines/chunk
    (500_000,  float("inf"), 1_000),  # huge   files  → 1 000 lines/chunk
]


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def load_and_chunk(file_path: str, file_name: str) -> list[list[str]]:
    """
    Read a file of any supported type, split into dynamic chunks.

    Returns
    -------
    list[list[str]]  – outer list = chunks, inner list = lines/rows in chunk
    """
    ext = Path(file_name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    logger.info("Loading file '%s' (ext=%s)", file_name, ext)

    # ── Route to the correct reader ───────────────────────────────────────────
    if ext in (".csv", ".tsv"):
        lines = _read_csv(file_path, ext)
    elif ext == ".json":
        lines = _read_json(file_path)
    elif ext in (".xml", ".html"):
        lines = _read_xml_html(file_path)
    elif ext == ".pdf":
        lines = _read_pdf(file_path)
    elif ext == ".docx":
        lines = _read_docx(file_path)
    elif ext == ".xlsx":
        lines = _read_xlsx(file_path)
    else:
        # .txt .log .md .text — generic text
        lines = _read_text(file_path)

    total_lines = len(lines)
    chunk_size  = _dynamic_chunk_size(total_lines)
    chunks      = _split_into_chunks(lines, chunk_size)

    logger.info(
        "File '%s': %d lines → chunk_size=%d → %d chunks",
        file_name, total_lines, chunk_size, len(chunks)
    )
    return chunks


def get_total_lines(file_path: str, file_name: str) -> int:
    """Quick line count without full parse (used to decide worker count)."""
    ext = Path(file_name).suffix.lower()
    if ext in (".pdf", ".docx", ".xlsx"):
        return len(load_and_chunk(file_path, file_name))   # full parse needed
    return _count_lines(file_path)


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC CHUNK SIZE CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

def _dynamic_chunk_size(total_lines: int) -> int:
    """Return chunk size in lines based on total file line count."""
    for lo, hi, size in CHUNK_THRESHOLDS:
        if lo <= total_lines < hi:
            return size
    return 1_000   # fallback


def _split_into_chunks(lines: list, chunk_size: int) -> list[list[str]]:
    """Slice list into sub-lists of `chunk_size` lines each."""
    return [lines[i: i + chunk_size] for i in range(0, len(lines), chunk_size)]


# ─────────────────────────────────────────────────────────────────────────────
# FILE READERS
# ─────────────────────────────────────────────────────────────────────────────

def _detect_encoding(file_path: str) -> str:
    """Sniff file encoding using chardet if available, otherwise fall back to utf-8."""
    if not _HAS_CHARDET:
        return "utf-8"
    with open(file_path, "rb") as f:
        raw = f.read(min(100_000, os.path.getsize(file_path)))
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def _count_lines(file_path: str) -> int:
    enc = _detect_encoding(file_path)
    count = 0
    with open(file_path, "r", encoding=enc, errors="replace") as f:
        for _ in f:
            count += 1
    return count


def _read_text(file_path: str) -> list[str]:
    """Stream any plain-text file line by line (memory-safe for huge files)."""
    enc = _detect_encoding(file_path)
    lines = []
    with open(file_path, "r", encoding=enc, errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if stripped:                # skip blank lines
                lines.append(stripped)
    return lines


def _read_csv(file_path: str, ext: str) -> list[str]:
    """
    CSV / TSV reader.
    Each row is converted to a plain string for uniform downstream processing.
    """
    enc = _detect_encoding(file_path)
    delimiter = "\t" if ext == ".tsv" else ","
    lines = []
    with open(file_path, "r", encoding=enc, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            text = " ".join(cell.strip() for cell in row if cell.strip())
            if text:
                lines.append(text)
    return lines


def _read_json(file_path: str) -> list[str]:
    """
    JSON reader – supports:
      • Array of strings
      • Array of objects (values joined)
      • Single object (values joined)
      • Newline-delimited JSON (NDJSON)
    """
    enc = _detect_encoding(file_path)
    lines = []
    try:
        with open(file_path, "r", encoding=enc, errors="replace") as f:
            data = json.load(f)

        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    lines.append(item.strip())
                elif isinstance(item, dict):
                    text = " ".join(str(v) for v in item.values() if v)
                    if text.strip():
                        lines.append(text.strip())
        elif isinstance(data, dict):
            text = " ".join(str(v) for v in data.values() if v)
            if text.strip():
                lines.append(text.strip())

    except json.JSONDecodeError:
        # Try NDJSON
        with open(file_path, "r", encoding=enc, errors="replace") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                    if isinstance(obj, str):
                        lines.append(obj)
                    elif isinstance(obj, dict):
                        text = " ".join(str(v) for v in obj.values() if v)
                        if text.strip():
                            lines.append(text.strip())
                except Exception:
                    lines.append(raw_line)

    return lines


def _read_xml_html(file_path: str) -> list[str]:
    """Extract visible text from XML / HTML by stripping tags."""
    enc = _detect_encoding(file_path)
    with open(file_path, "r", encoding=enc, errors="replace") as f:
        content = f.read()

    # Remove tags
    text = re.sub(r"<[^>]+>", " ", content)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Split into sentences (rough)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def _read_pdf(file_path: str) -> list[str]:
    """Extract text from PDF page by page."""
    try:
        import PyPDF2
        lines = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                for line in page_text.splitlines():
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
        return lines
    except ImportError:
        logger.warning("PyPDF2 not installed. Install it: pip install PyPDF2")
        return []


def _read_docx(file_path: str) -> list[str]:
    """Extract paragraphs from a Word document."""
    try:
        from docx import Document
        doc = Document(file_path)
        return [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    except ImportError:
        logger.warning("python-docx not installed. Install it: pip install python-docx")
        return []


def _read_xlsx(file_path: str) -> list[str]:
    """Read all cells from an Excel file row by row."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                text = " ".join(str(cell) for cell in row if cell is not None)
                text = text.strip()
                if text:
                    lines.append(text)
        wb.close()
        return lines
    except ImportError:
        logger.warning("openpyxl not installed. Install it: pip install openpyxl")
        return []