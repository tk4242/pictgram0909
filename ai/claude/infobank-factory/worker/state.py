"""ジョブの状態を SQLite に持つ。プロセスが落ちても再起動で続きから再開するため。"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.sqlite3"

# 設計書§34の状態機械
STATES = [
    "NEW", "RULES_LOADED", "SOURCE_LOADED", "RESEARCHING", "EVIDENCE_READY",
    "DRAFT_READY", "FACTCHECK_PASSED", "MEMBERSHIP_BUILT", "VISUAL_BRIEF_READY",
    "IMAGE_READY", "THUMBNAIL_READY", "PPTX_READY", "QA_PASSED",
    "READY_FOR_HUMAN_REVIEW", "APPROVED",
]
# ここから先へ自動で進めてはいけない（設計書§42-24）
HUMAN_GATE = "READY_FOR_HUMAN_REVIEW"

FAILURES = {
    "RULE_CHANGE_DETECTED", "SOURCE_CONFLICT", "UNSUPPORTED_CLAIM", "TITLE_FAIL",
    "MEMBER_FAIL", "MAGNIFIC_FAIL", "CANVA_FAIL", "PPTX_FAIL", "QA_FAIL",
    "BRAND_NAME_CONFLICT", "UNKNOWN_REQUIREMENT", "NOT_IMPLEMENTED",
}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")   # 起動中に落ちてもDBが壊れにくい
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id      TEXT PRIMARY KEY,
            source_url  TEXT UNIQUE,
            state       TEXT NOT NULL,
            failure     TEXT,
            detail      TEXT,
            attempts    INTEGER NOT NULL DEFAULT 0,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transitions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id    TEXT NOT NULL,
            state     TEXT NOT NULL,
            failure   TEXT,
            detail    TEXT,
            at        REAL NOT NULL
        );
    """)
    return conn


def claim_new(conn, job_id, source_url):
    """同じ記事を二重に処理しない（設計書§37）。既存なら False。"""
    now = time.time()
    try:
        conn.execute(
            "INSERT INTO jobs (job_id, source_url, state, created_at, updated_at)"
            " VALUES (?, ?, 'NEW', ?, ?)", (job_id, source_url, now, now))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def advance(conn, job_id, state, failure=None, detail=None):
    now = time.time()
    conn.execute(
        "UPDATE jobs SET state=?, failure=?, detail=?, updated_at=?,"
        " attempts=attempts+1 WHERE job_id=?",
        (state, failure, detail, now, job_id))
    conn.execute(
        "INSERT INTO transitions (job_id, state, failure, detail, at)"
        " VALUES (?,?,?,?,?)", (job_id, state, failure, detail, now))
    conn.commit()


def pending(conn):
    """人間待ち・失敗中を除いた、次に進められるジョブ。"""
    cur = conn.execute(
        "SELECT job_id, source_url, state FROM jobs"
        " WHERE failure IS NULL AND state NOT IN (?, 'APPROVED')"
        " ORDER BY created_at", (HUMAN_GATE,))
    return cur.fetchall()
