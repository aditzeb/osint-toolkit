"""Local SQLite Full-Text Search (FTS5) Engine for Private / Leaked / Custom Datasets.

Features:
- Stores records in `data/local_osint.db` (strictly .gitignored for user privacy).
- Full-Text Search (FTS5) index over Name, NIK, Phone, Email, Plat, and Extra fields.
- Fast bulk importer for CSV, TSV, JSON, and JSONL files.
- Sub-second queries across millions of rows.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "local_osint.db"


def get_db_connection() -> sqlite3.Connection:
    """Connect to the local SQLite database and ensure FTS5 tables exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS imported_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE,
                record_count INTEGER,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
                name,
                nik,
                phone,
                email,
                plate,
                extra,
                source_file,
                tokenize='unicode61'
            );
        """)
    return conn


def _classify_columns(headers: List[str]) -> Dict[str, Optional[int]]:
    """Map detected header names to standard fields."""
    mapping: Dict[str, Optional[int]] = {
        "name": None,
        "nik": None,
        "phone": None,
        "email": None,
        "plate": None,
    }

    for idx, raw_h in enumerate(headers):
        h = raw_h.strip().lower().replace("_", "").replace(" ", "").replace("-", "")
        if mapping["nik"] is None and ("nik" in h or "ktp" in h or "noktp" in h):
            mapping["nik"] = idx
        elif mapping["phone"] is None and ("phone" in h or "hp" in h or "nohp" in h or "telepon" in h or "telp" in h or "msisdn" in h or "mobile" in h):
            mapping["phone"] = idx
        elif mapping["email"] is None and ("email" in h or "mail" in h or "surel" in h):
            mapping["email"] = idx
        elif mapping["name"] is None and ("name" in h or "nama" in h or "fullname" in h or "namalengkap" in h):
            mapping["name"] = idx
        elif mapping["plate"] is None and ("plate" in h or "plat" in h or "nopol" in h or "tnkb" in h or "nomorpolisi" in h):
            mapping["plate"] = idx

    return mapping


def import_csv_file(file_path: Path) -> Tuple[int, str]:
    """Import a CSV or TSV file into the local FTS5 database."""
    if not file_path.exists():
        return 0, f"File not found: {file_path}"

    conn = get_db_connection()
    filename = file_path.name

    # Check if already imported
    cur = conn.cursor()
    cur.execute("SELECT id FROM imported_sources WHERE filename = ?", (filename,))
    if cur.fetchone():
        return 0, f"File '{filename}' has already been imported. Skipping."

    inserted = 0
    batch_size = 5000
    batch: List[Tuple[str, str, str, str, str, str, str]] = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)
            delimiter = "\t" if "\t" in sample and sample.count("\t") > sample.count(",") else ","
            reader = csv.reader(f, delimiter=delimiter)

            try:
                headers = next(reader)
            except StopIteration:
                return 0, "File is empty."

            col_map = _classify_columns(headers)

            for row in reader:
                if not row or not any(row):
                    continue

                def get_val(key: str) -> str:
                    idx = col_map.get(key)
                    if idx is not None and idx < len(row):
                        return row[idx].strip()
                    return ""

                name = get_val("name")
                nik = get_val("nik")
                phone = get_val("phone")
                email = get_val("email")
                plate = get_val("plate")

                # Collect extra fields
                extra_parts = []
                for idx, val in enumerate(row):
                    if idx not in col_map.values() and val.strip():
                        h_name = headers[idx] if idx < len(headers) else f"col_{idx}"
                        extra_parts.append(f"{h_name}: {val.strip()}")
                extra = " | ".join(extra_parts)

                # Fallback: if no recognized columns, put row content in extra
                if not any([name, nik, phone, email, plate]):
                    extra = " | ".join(f"{h}: {v.strip()}" for h, v in zip(headers, row) if v.strip())

                batch.append((name, nik, phone, email, plate, extra, filename))
                inserted += 1

                if len(batch) >= batch_size:
                    with conn:
                        conn.executemany(
                            "INSERT INTO records_fts (name, nik, phone, email, plate, extra, source_file) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            batch
                        )
                    batch = []

            if batch:
                with conn:
                    conn.executemany(
                        "INSERT INTO records_fts (name, nik, phone, email, plate, extra, source_file) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        batch
                    )

        with conn:
            conn.execute(
                "INSERT INTO imported_sources (filename, record_count) VALUES (?, ?)",
                (filename, inserted)
            )

        return inserted, f"Successfully imported {inserted:,} records from '{filename}'"

    except Exception as e:
        return inserted, f"Import error: {e}"
    finally:
        conn.close()


def search_local_db(query: str, limit: int = 50) -> List[Dict[str, str]]:
    """Search records across all fields using SQLite FTS5."""
    if not DB_PATH.exists():
        return []

    clean_query = query.strip()
    if not clean_query:
        return []

    conn = get_db_connection()
    cur = conn.cursor()
    results: List[Dict[str, str]] = []

    # Format query for FTS5 (escape special chars)
    # Quote individual words with prefix wildcards
    words = clean_query.replace('"', '').replace("'", "").split()
    fts_expr = " AND ".join(f'"{w}"*' for w in words if w)

    try:
        cur.execute(
            """
            SELECT name, nik, phone, email, plate, extra, source_file
            FROM records_fts
            WHERE records_fts MATCH ?
            LIMIT ?
            """,
            (fts_expr, limit)
        )
        for row in cur.fetchall():
            results.append({
                "name": row[0] or "",
                "nik": row[1] or "",
                "phone": row[2] or "",
                "email": row[3] or "",
                "plate": row[4] or "",
                "extra": row[5] or "",
                "source_file": row[6] or "",
            })
    except sqlite3.OperationalError:
        # Fallback to standard LIKE if FTS expression failed
        like_query = f"%{clean_query}%"
        cur.execute(
            """
            SELECT name, nik, phone, email, plate, extra, source_file
            FROM records_fts
            WHERE name LIKE ? OR nik LIKE ? OR phone LIKE ? OR email LIKE ? OR plate LIKE ? OR extra LIKE ?
            LIMIT ?
            """,
            (like_query, like_query, like_query, like_query, like_query, like_query, limit)
        )
        for row in cur.fetchall():
            results.append({
                "name": row[0] or "",
                "nik": row[1] or "",
                "phone": row[2] or "",
                "email": row[3] or "",
                "plate": row[4] or "",
                "extra": row[5] or "",
                "source_file": row[6] or "",
            })
    finally:
        conn.close()

    return results


def get_db_stats() -> Dict[str, Any]:
    """Retrieve statistical metadata about the local database."""
    if not DB_PATH.exists():
        return {"total_records": 0, "sources": [], "file_size_mb": 0.0}

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM records_fts")
        total = cur.fetchone()[0]

        cur.execute("SELECT filename, record_count, imported_at FROM imported_sources ORDER BY id DESC")
        sources = [
            {"filename": r[0], "count": r[1], "date": r[2]}
            for r in cur.fetchall()
        ]

        size_mb = DB_PATH.stat().st_size / (1024 * 1024)
        return {
            "total_records": total,
            "sources": sources,
            "file_size_mb": round(size_mb, 2),
        }
    except Exception:
        return {"total_records": 0, "sources": [], "file_size_mb": 0.0}
    finally:
        conn.close()
