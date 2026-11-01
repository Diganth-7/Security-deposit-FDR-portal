"""
Versioned, idempotent schema migrations (no external tool needed).

How it works
* ``schema_migrations`` records which versions have run.
* ``run_migrations(engine)`` first creates any tables that do not exist yet
  (a fresh database gets the latest schema), then applies each pending
  migration in order. Every migration checks the live schema before changing
  it, so running twice, or on a database that is already current, is safe.
* Existing rows are always preserved; no migration drops user data.

Run manually:  python -m backend.app.migrations
"""
import logging
from datetime import datetime, timezone
from typing import Callable, List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from backend.app.database import Base

logger = logging.getLogger("aicte_fdr.migrations")


def _cols(conn: Connection, table: str) -> dict:
    insp = inspect(conn)
    if not insp.has_table(table):
        return {}
    return {c["name"]: c for c in insp.get_columns(table)}


def _add_column(conn: Connection, table: str, name: str, ddl_type: str) -> None:
    """ALTER TABLE ... ADD COLUMN if the table exists and the column does not."""
    cols = _cols(conn, table)
    if cols and name not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))
        logger.info("Added %s.%s", table, name)


def _is_pg(conn: Connection) -> bool:
    return conn.dialect.name == "postgresql"


def _create_index(conn: Connection, name: str, table: str, column: str) -> None:
    if _cols(conn, table) and column in _cols(conn, table):
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"))


# --------------------------------------------------------------------------- #
# Migrations
# --------------------------------------------------------------------------- #
def m0002_audit_columns(conn: Connection) -> None:
    """Audit log: add actor role, entity, institution, correlation and before/after."""
    t = "audit_logs"
    _add_column(conn, t, "actor_role", "VARCHAR(30)")
    _add_column(conn, t, "entity_type", "VARCHAR(50)")
    _add_column(conn, t, "entity_id", "INTEGER")
    _add_column(conn, t, "institution_id", "INTEGER")
    _add_column(conn, t, "before_data", "TEXT")
    _add_column(conn, t, "after_data", "TEXT")
    _add_column(conn, t, "correlation_id", "VARCHAR(64)")
    cols = _cols(conn, t)
    if not cols:
        return
    # Back-fill from the FDR the entry belongs to (history written before this version).
    conn.execute(text(
        "UPDATE audit_logs SET entity_type = 'DEPOSIT', entity_id = deposit_id "
        "WHERE entity_type IS NULL AND deposit_id IS NOT NULL"))
    conn.execute(text(
        "UPDATE audit_logs SET institution_id = (SELECT d.institution_id FROM deposits d WHERE d.id = audit_logs.deposit_id) "
        "WHERE institution_id IS NULL AND deposit_id IS NOT NULL"))
    conn.execute(text(
        "UPDATE audit_logs SET actor_role = (SELECT CAST(u.role AS VARCHAR(30)) FROM users u WHERE u.id = audit_logs.actor_id) "
        "WHERE actor_role IS NULL AND actor_id IS NOT NULL"))
    for idx, col in (("ix_audit_logs_entity_type", "entity_type"), ("ix_audit_logs_entity_id", "entity_id"),
                     ("ix_audit_logs_institution_id", "institution_id"), ("ix_audit_logs_correlation_id", "correlation_id")):
        _create_index(conn, idx, t, col)


def m0003_audit_deposit_nullable(conn: Connection) -> None:
    """Audit rows must outlive an FDR: deposit_id becomes nullable and no longer cascades."""
    cols = _cols(conn, "audit_logs")
    if not cols or cols["deposit_id"].get("nullable", True):
        return
    if _is_pg(conn):
        conn.execute(text("ALTER TABLE audit_logs ALTER COLUMN deposit_id DROP NOT NULL"))
        for fk in inspect(conn).get_foreign_keys("audit_logs"):
            if fk["constrained_columns"] == ["deposit_id"] and fk.get("name"):
                conn.execute(text(f'ALTER TABLE audit_logs DROP CONSTRAINT "{fk["name"]}"'))
        conn.execute(text(
            "ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_deposit_id_fkey "
            "FOREIGN KEY (deposit_id) REFERENCES deposits (id) ON DELETE SET NULL"))
    else:
        _rebuild_sqlite_table(conn, "audit_logs")


def _rebuild_sqlite_table(conn: Connection, table: str) -> None:
    """SQLite cannot alter constraints: rebuild the table from the current model, copying every row."""
    old = f"{table}__old"
    for idx in inspect(conn).get_indexes(table):
        if idx.get("name"):
            conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
    old_cols = list(_cols(conn, table))
    conn.execute(text(f"ALTER TABLE {table} RENAME TO {old}"))
    Base.metadata.tables[table].create(bind=conn)
    new_cols = set(_cols(conn, table))
    shared = ", ".join(c for c in old_cols if c in new_cols)
    conn.execute(text(f"INSERT INTO {table} ({shared}) SELECT {shared} FROM {old}"))
    conn.execute(text(f"DROP TABLE {old}"))


def m0004_money_numeric(conn: Connection) -> None:
    """deposits.amount FLOAT -> NUMERIC(15,2). SQLite already stores NUMERIC affinity values exactly enough."""
    cols = _cols(conn, "deposits")
    if cols and _is_pg(conn):
        type_name = str(cols["amount"]["type"]).upper()
        if "NUMERIC" not in type_name and "DECIMAL" not in type_name:
            conn.execute(text(
                "ALTER TABLE deposits ALTER COLUMN amount TYPE NUMERIC(15,2) USING ROUND(amount::numeric, 2)"))


def m0005_user_lockout(conn: Connection) -> None:
    """Users: brute-force lockout and last-login tracking."""
    _add_column(conn, "users", "failed_login_attempts", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "users", "locked_until", "TIMESTAMP")
    _add_column(conn, "users", "last_login_at", "TIMESTAMP")


def m0006_request_previous_status(conn: Connection) -> None:
    """Approval requests remember the FDR status they replaced, so reject/cancel restores it exactly."""
    _add_column(conn, "approval_requests", "previous_deposit_status", "VARCHAR(50)")


MIGRATIONS: List[Tuple[str, Callable[[Connection], None]]] = [
    ("0002_audit_columns", m0002_audit_columns),
    ("0003_audit_deposit_nullable", m0003_audit_deposit_nullable),
    ("0004_money_numeric", m0004_money_numeric),
    ("0005_user_lockout", m0005_user_lockout),
    ("0006_request_previous_status", m0006_request_previous_status),
]


def run_migrations(engine: Engine) -> List[str]:
    """Creates missing tables, then applies pending migrations. Returns versions applied."""
    # Import models so every table is registered on Base.metadata.
    import backend.app.models  # noqa: F401

    applied: List[str] = []
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(100) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"))
    Base.metadata.create_all(bind=engine)  # new tables only; never alters existing ones

    for version, fn in MIGRATIONS:
        with engine.begin() as conn:
            done = conn.execute(text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": version}).first()
            if done:
                continue
            fn(conn)
            conn.execute(text("INSERT INTO schema_migrations (version, applied_at) VALUES (:v, :t)"),
                         {"v": version, "t": datetime.now(timezone.utc).isoformat()})
            applied.append(version)
            logger.info("Applied migration %s", version)
    return applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from backend.app.database import engine as _engine
    done = run_migrations(_engine)
    print("Applied:", ", ".join(done) if done else "nothing (already up to date)")
