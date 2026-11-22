"""Database fixtures.

Each pytest process gets its own database, copied from a migrated template
with CREATE DATABASE ... TEMPLATE. That copy takes well under a second, where
running the migrations takes far longer. Each test then runs inside a
transaction that is rolled back, so tests never see each other's rows.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import ci_config
import psycopg
import pytest
from app.db import database_url, get_conn
from app.main import app
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
BASE_DB = os.environ.get("FASTCI_BASE_DB", "acme_test_base")


def _admin() -> psycopg.Connection:
    return psycopg.connect(database_url("postgres"), autocommit=True)


def _template_exists() -> bool:
    with _admin() as conn:
        return conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (BASE_DB,)).fetchone() is not None


def _ensure_template() -> None:
    """Locally, build or restore the template on demand. In CI it must already exist."""
    if _template_exists():
        return
    if os.environ.get("FASTCI_REQUIRE_TEMPLATE") == "1":
        pytest.exit(f"template database {BASE_DB!r} is missing; the cache restore step did not run", returncode=3)
    cfg = ci_config.load(REPO / "fast-ci.toml", "backend")
    env = {
        **os.environ,
        "FASTCI_FINGERPRINT": cfg["migration_fingerprint"],
        "FASTCI_MIGRATE_CMD": cfg["migrate_command"],
        "FASTCI_BASE_DB": BASE_DB,
    }
    subprocess.run([str(REPO / "scripts/test_db.sh"), "ensure"], check=True, cwd=BACKEND, env=env)


@pytest.fixture(scope="session")
def database() -> Iterator[str]:
    _ensure_template()
    name = f"acme_test_{os.environ.get('FASTCI_SHARD', 'local')}_{os.getpid()}"
    with _admin() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
        conn.execute(f'CREATE DATABASE "{name}" TEMPLATE "{BASE_DB}"')
    yield name
    with _admin() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def _session_conn(database: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url(database), row_factory=dict_row) as conn:
        yield conn


@pytest.fixture
def conn(_session_conn: psycopg.Connection) -> Iterator[psycopg.Connection]:
    with _session_conn.transaction(force_rollback=True):
        yield _session_conn


@pytest.fixture
def client(conn: psycopg.Connection) -> Iterator[TestClient]:
    app.dependency_overrides[get_conn] = lambda: conn
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
