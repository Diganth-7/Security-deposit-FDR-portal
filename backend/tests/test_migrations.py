"""Upgrading an older database must keep data and be safe to run repeatedly."""
from sqlalchemy import create_engine, text, inspect

from backend.app.database import Base
from backend.app.migrations import run_migrations
import backend.app.models  # noqa: F401


def _make_old_database(path):
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=eng)
    with eng.begin() as c:
        # Recreate the pre-upgrade shapes of the tables that changed.
        c.execute(text("DROP TABLE audit_logs"))
        c.execute(text(
            "CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER, "
            "action VARCHAR(100) NOT NULL, deposit_id INTEGER NOT NULL, details TEXT, timestamp DATETIME NOT NULL)"))
        for col in ("failed_login_attempts", "locked_until", "last_login_at"):
            c.execute(text(f"ALTER TABLE users DROP COLUMN {col}"))
        c.execute(text("DELETE FROM schema_migrations")) if inspect(c).has_table("schema_migrations") else None
    return eng


def test_upgrade_preserves_rows_and_is_idempotent(tmp_path):
    eng = _make_old_database(tmp_path / "old.db")
    with eng.begin() as c:
        c.execute(text("INSERT INTO audit_logs (actor_id, action, deposit_id, details, timestamp) "
                       "VALUES (NULL, 'FDR_SUBMITTED', 7, 'legacy entry', '2026-01-01 00:00:00')"))

    first = run_migrations(eng)
    assert "0002_audit_columns" in first and "0005_user_lockout" in first

    with eng.connect() as c:
        row = c.execute(text("SELECT action, details, entity_type, entity_id FROM audit_logs")).one()
        assert tuple(row) == ("FDR_SUBMITTED", "legacy entry", "DEPOSIT", 7)
        cols = {col["name"]: col for col in inspect(c).get_columns("audit_logs")}
        assert cols["deposit_id"]["nullable"] is True
        assert {"actor_role", "correlation_id", "before_data", "after_data"} <= set(cols)
        user_cols = {col["name"] for col in inspect(c).get_columns("users")}
        assert {"failed_login_attempts", "locked_until"} <= user_cols

    assert run_migrations(eng) == []  # second run changes nothing
