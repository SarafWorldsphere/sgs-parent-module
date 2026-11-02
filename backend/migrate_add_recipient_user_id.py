"""
migrate_add_recipient_user_id.py
────────────────────────────────
One-time migration: adds recipient_user_id to the support_tickets table, and
backfills it from recipient_name where that name matches exactly one user.

WHY
───
A conversation records who the parent wrote to as `recipient_name` — a string.
The recipient picker already resolves a real users_masters.user_id and then
throws it away. That leaves no id to join on, so "show this teacher their
conversations" has to match on a name, and two teachers sharing a name would
read each other's messages about a child. This column is the id link.

USAGE
─────
Run once, manually, in any environment where the column is missing:

    python migrate_add_recipient_user_id.py

Safe to re-run: checks whether the column exists before issuing any DDL, and
the backfill only fills rows that are still NULL.

DO NOT import or call this from main.py or any application code.
Schema changes must not run automatically on application startup.

NOTE ON PERMISSIONS
───────────────────
ALTER TABLE needs ownership. If the application's database user does not own
the table, run this as the owner — the same workaround the recipient_name
migration needed.
"""

import os
import sys
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/mydb_sgs")
DB_PREFIX    = os.getenv("DB_TABLE_PREFIX", "")

TABLE_NAME  = f"{DB_PREFIX}support_tickets"
USERS_TABLE = f"{DB_PREFIX}users_masters"
COLUMN_NAME = "recipient_user_id"
INDEX_NAME  = f"ix_{TABLE_NAME}_recipient_user_id"


def column_exists(conn) -> bool:
    """
    Check information_schema.columns — requires only SELECT privilege, not ownership.
    Works with both prefixed (sgs_) and unprefixed table names.
    """
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "  AND table_name   = :table "
            "  AND column_name  = :col "
            "LIMIT 1"
        ),
        {"table": TABLE_NAME, "col": COLUMN_NAME},
    ).fetchone()
    return row is not None


def backfill(conn) -> int:
    """
    Fill the id from recipient_name, but only where the name identifies exactly
    one user. An ambiguous name is left NULL on purpose: guessing which of two
    teachers a parent wrote to is worse than admitting we do not know, and the
    faculty side treats NULL as "not addressed to me".
    """
    result = conn.execute(
        text(
            f"""
            UPDATE {TABLE_NAME} t
               SET {COLUMN_NAME} = u.user_id
              FROM {USERS_TABLE} u
             WHERE t.{COLUMN_NAME} IS NULL
               AND t.recipient_name IS NOT NULL
               AND lower(trim(u.full_name)) = lower(trim(t.recipient_name))
               AND (
                    SELECT count(*) FROM {USERS_TABLE} u2
                     WHERE lower(trim(u2.full_name)) = lower(trim(t.recipient_name))
                   ) = 1
            """
        )
    )
    return result.rowcount or 0


def remaining_unmatched(conn) -> int:
    row = conn.execute(
        text(f"SELECT count(*) FROM {TABLE_NAME} WHERE {COLUMN_NAME} IS NULL")
    ).fetchone()
    return row[0] if row else 0


def main() -> int:
    log.info("=" * 60)
    log.info("  Migration: add %s.%s", TABLE_NAME, COLUMN_NAME)
    log.info("  DB_TABLE_PREFIX : %r", DB_PREFIX or "(none — local dev)")
    log.info("=" * 60)

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        if column_exists(conn):
            log.info("  ✓  Column '%s' already exists in '%s'.", COLUMN_NAME, TABLE_NAME)
        else:
            log.info("  Column '%s' not found — adding it now ...", COLUMN_NAME)
            conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {COLUMN_NAME} BIGINT"))
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON {TABLE_NAME} ({COLUMN_NAME})")
            )
            conn.commit()
            log.info("  ✓  Column and index added to '%s'.", TABLE_NAME)

        log.info("  Backfilling from recipient_name where the name is unambiguous ...")
        filled = backfill(conn)
        conn.commit()
        log.info("  ✓  Backfilled %d row(s).", filled)

        left = remaining_unmatched(conn)
        if left:
            log.info(
                "  %d row(s) still have no recipient_user_id — either the name "
                "matches no user, or it matches more than one. Those "
                "conversations will not appear for any teacher until the "
                "recipient is set by hand.",
                left,
            )

    log.info("=" * 60)
    log.info("  Migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
