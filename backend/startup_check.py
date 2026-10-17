"""
startup_check.py — RDS Table Existence Validator
=================================================
Validates that every table the application actively queries exists in the
connected database before uvicorn starts serving traffic.

WHY THIS EXISTS
───────────────
The shared database uses unprefixed table names. Some older tables
(e.g. teacher_parent_interaction) are not part of the current schema.
This script reports a missing required table before the first request.

HOW TO USE
──────────
Option A — run before uvicorn (recommended in CI/deploy scripts):

    python startup_check.py
    # exits 0 on success, 1 on failure

Option B — import and call from main.py so the check runs automatically:

    from startup_check import run_startup_checks
    run_startup_checks()   # raises RuntimeError if a required table is missing

TABLES CHECKED
──────────────
Required tables (app will NOT start if any are absent):
    class_master, student_master, parent_master, parent_student_map,
    teacher_master, subject_master, chapter_master, assignment_master,
    student_submission, quiz_master, quiz_response, notice_board,
    support_tickets, ticket_messages

Legacy / optional tables (warning only — app continues):
    teacher_parent_interaction  — removed from SGS RDS; remarks now use
                                  ticket_messages with sender_type='TEACHER'
    attendance_master           — attendance module disabled in parent portal
    call_requests               — replaced by Communication Center
    leave_requests              — replaced by Communication Center
    school_events               — events feature not in current scope
    chat_threads, chat_messages — replaced by Communication Center
"""

import os
import sys
import logging

from sqlalchemy import text
from database import engine

log = logging.getLogger(__name__)

# ── Table manifests ───────────────────────────────────────────────────────────

# The app will refuse to start if any of these are missing.
REQUIRED_TABLES = [
    "users_masters",        # FK root for teacher/staff — must exist before seeding
    "class_master",
    "student_master",
    "parent_master",
    "parent_student_map",
    "teacher_master",
    "subject_master",
    "chapter_master",
    "assignment_master",
    "student_submission",
    "quiz_master",
    "quiz_response",
    "notice_board",
    "support_tickets",
    "ticket_messages",
    "assessments",           # Assessments module — must exist before serving /assessments/
    "assessment_results",    # Assessments module — stores per-student results
]

# Missing legacy tables generate a WARNING but do NOT block startup.
LEGACY_TABLES = [
    "teacher_parent_interaction",   # absent on SGS RDS — remarks replaced
    "attendance_master",            # attendance module disabled
    "call_requests",                # replaced by Communication Center
    "leave_requests",               # replaced by Communication Center
    "school_events",                # events feature out of scope
    "chat_threads",                 # replaced by Communication Center
    "chat_messages",                # replaced by Communication Center
]


def _existing_tables(schema: str = "public") -> set:
    """
    Return the set of table names that currently exist in *schema*.

    Uses information_schema.tables. Table names are unprefixed.
    """
    sql = text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_type = 'BASE TABLE'"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"schema": schema}).fetchall()
    return {row[0] for row in rows}


def run_startup_checks(raise_on_error: bool = True) -> bool:
    """
    Validate that all required tables exist in the connected database.

    Parameters
    ----------
    raise_on_error : bool
        If True (default) raise RuntimeError when required tables are absent.
        Set to False to get a boolean return value instead (useful for tests).

    Returns
    -------
    bool
        True  — all required tables present (startup is safe)
        False — one or more required tables missing (only when raise_on_error=False)

    Raises
    ------
    RuntimeError
        When raise_on_error=True and at least one required table is missing.
    """
    _raw_url = os.getenv("DATABASE_URL", "")
    if _raw_url:
        try:
            from urllib.parse import urlparse, urlunparse
            _p = urlparse(_raw_url)
            _redacted = _p._replace(netloc=_p.hostname + (f":{_p.port}" if _p.port else ""))
            db_url_hint = urlunparse(_redacted)
        except Exception:
            db_url_hint = "<DATABASE_URL set>"
    else:
        db_url_hint = "DATABASE_URL not set"

    log.info("=" * 60)
    log.info("  Startup table check")
    log.info("  Database  : %s", db_url_hint)
    log.info("=" * 60)

    existing = _existing_tables()

    # ── Required tables ───────────────────────────────────────────────────
    missing_required = []
    for name in REQUIRED_TABLES:
        if name in existing:
            log.info("  ✓  %-40s  OK", name)
        else:
            log.error("  ✗  %-40s  MISSING", name)
            missing_required.append(name)

    # ── Legacy / optional tables ─────────────────────────────────────────
    for name in LEGACY_TABLES:
        if name in existing:
            log.warning(
                "  ⚠  %-40s  present (legacy — not actively queried)",
                name,
            )
        else:
            log.info(
                "  –  %-40s  absent  (legacy)",
                name,
            )

    log.info("=" * 60)

    if missing_required:
        msg = (
            f"Startup check FAILED — {len(missing_required)} required table(s) "
            f"not found in the database:\n  " +
            "\n  ".join(missing_required) +
            "\n\nApply saraswati-tenant-kit before starting this API."
        )
        log.error(msg)
        if raise_on_error:
            raise RuntimeError(msg)
        return False

    log.info("  All required tables are present. Startup is safe.")
    return True


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    ok = run_startup_checks(raise_on_error=False)
    sys.exit(0 if ok else 1)
