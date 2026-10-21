import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "kidtrace.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)

MALAYSIA_TIME = timezone(timedelta(hours=8))


def current_time():
    return datetime.now(MALAYSIA_TIME).replace(
        tzinfo=None
    ).isoformat(timespec="seconds")


def initialise_database():
    with sqlite3.connect(DB_PATH, timeout=30) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS search_cases (
                case_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_seen_location TEXT NOT NULL,
                last_seen_at TEXT,
                status TEXT NOT NULL DEFAULT 'Searching',
                latest_location TEXT,
                match_count INTEGER NOT NULL DEFAULT 0,
                reviewed_at TEXT,
                dispatched_at TEXT,
                resolved_at TEXT
            )
        """)


def create_case(last_seen_location, last_seen_at, match_count):
    initialise_database()

    case_id = f"KT-{uuid4().hex[:12].upper()}"

    with sqlite3.connect(DB_PATH, timeout=30) as connection:
        connection.execute(
            """
            INSERT INTO search_cases (
                case_id,
                created_at,
                last_seen_location,
                last_seen_at,
                status,
                match_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                current_time(),
                last_seen_location,
                last_seen_at,
                "Searching",
                int(match_count),
            ),
        )

    return case_id


def review_case(case_id, latest_location):
    with sqlite3.connect(DB_PATH, timeout=30) as connection:
        result = connection.execute(
            """
            UPDATE search_cases
            SET
                status = 'Match Reviewed',
                latest_location = ?,
                reviewed_at = COALESCE(reviewed_at, ?)
            WHERE case_id = ?
              AND resolved_at IS NULL
            """,
            (
                latest_location,
                current_time(),
                case_id,
            ),
        )

        if result.rowcount != 1:
            raise ValueError("The active case could not be updated.")


def dispatch_case(case_id):
    with sqlite3.connect(DB_PATH, timeout=30) as connection:
        result = connection.execute(
            """
            UPDATE search_cases
            SET
                status = 'Officer Dispatched',
                dispatched_at = COALESCE(dispatched_at, ?)
            WHERE case_id = ?
              AND reviewed_at IS NOT NULL
              AND resolved_at IS NULL
            """,
            (
                current_time(),
                case_id,
            ),
        )

        if result.rowcount != 1:
            raise ValueError("The active case could not be dispatched.")


def resolve_case(case_id):
    with sqlite3.connect(DB_PATH, timeout=30) as connection:
        result = connection.execute(
            """
            UPDATE search_cases
            SET
                status = 'Child Found',
                resolved_at = COALESCE(resolved_at, ?)
            WHERE case_id = ?
              AND reviewed_at IS NOT NULL
              AND resolved_at IS NULL
            """,
            (
                current_time(),
                case_id,
            ),
        )

        if result.rowcount != 1:
            raise ValueError("The active case could not be resolved.")