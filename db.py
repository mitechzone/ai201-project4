"""SQLite storage for Provenance Guard: content records + append-only audit log.

Schema mirrors planning.md (Storage and Audit Log):
  content   - one mutable row per submission (status flips on appeal)
  audit_log - append-only, one row per event (classification | appeal)
"""

import os
import sqlite3
import datetime

DB_PATH = os.getenv("PG_DB_PATH", "provenance.db")


def utcnow():
    """ISO-8601 UTC timestamp, e.g. 2026-06-28T14:32:10.123456+00:00."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS content (
                content_id   TEXT PRIMARY KEY,
                creator_id   TEXT NOT NULL,
                text         TEXT NOT NULL,
                attribution  TEXT,
                confidence   REAL,
                llm_score    REAL,
                stylo_score  REAL,
                label        TEXT,
                status       TEXT,
                created_at   TEXT,
                updated_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id          TEXT NOT NULL,
                creator_id          TEXT,
                timestamp           TEXT,
                event               TEXT,
                attribution         TEXT,
                confidence          REAL,
                llm_score           REAL,
                stylo_score         REAL,
                status              TEXT,
                appeal_reasoning    TEXT,
                appeal_evidence_url TEXT
            );
            """
        )


def record_classification(content_id, creator_id, text, attribution,
                          confidence, llm_score, stylo_score, label):
    """Insert the content row and its `classification` audit entry in one transaction."""
    ts = utcnow()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO content (content_id, creator_id, text, attribution,
                   confidence, llm_score, stylo_score, label, status,
                   created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'classified', ?, ?)""",
            (content_id, creator_id, text, attribution, confidence,
             llm_score, stylo_score, label, ts, ts),
        )
        conn.execute(
            """INSERT INTO audit_log (content_id, creator_id, timestamp, event,
                   attribution, confidence, llm_score, stylo_score, status)
               VALUES (?, ?, ?, 'classification', ?, ?, ?, ?, 'classified')""",
            (content_id, creator_id, ts, attribution, confidence,
             llm_score, stylo_score),
        )


def get_content(content_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM content WHERE content_id = ?", (content_id,)
        ).fetchone()
    return dict(row) if row else None


def record_appeal(content_id, creator_reasoning, evidence_url=None):
    """Flip the content's status to under_review and append an `appeal` audit entry.

    The appeal entry copies the original classification fields (attribution, scores) so it
    sits beside the original `classification` row for the same content_id in the log.
    Returns the content dict, or None if the content_id is unknown.
    """
    ts = utcnow()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM content WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        c = dict(row)
        conn.execute(
            "UPDATE content SET status='under_review', updated_at=? WHERE content_id=?",
            (ts, content_id),
        )
        conn.execute(
            """INSERT INTO audit_log (content_id, creator_id, timestamp, event,
                   attribution, confidence, llm_score, stylo_score, status,
                   appeal_reasoning, appeal_evidence_url)
               VALUES (?, ?, ?, 'appeal', ?, ?, ?, ?, 'under_review', ?, ?)""",
            (content_id, c["creator_id"], ts, c["attribution"], c["confidence"],
             c["llm_score"], c["stylo_score"], creator_reasoning, evidence_url),
        )
    return c


def get_log(limit=50):
    """Most recent audit entries first, as a list of plain dicts."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
