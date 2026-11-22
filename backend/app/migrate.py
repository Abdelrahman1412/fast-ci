"""Apply the SQL files in migrations/ in order, once each."""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from app.db import database_url

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS.glob("*.sql"))


def latest_migration() -> str:
    files = migration_files()
    return files[-1].stem if files else ""


def apply(url: str) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        for path in migration_files():
            if path.stem in done:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.stem,))
            applied.append(path.stem)
    return applied


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else database_url()
    for name in apply(url):
        print(f"applied {name}")
