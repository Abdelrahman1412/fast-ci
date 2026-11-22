"""Connection handling. One connection per request; tests swap in their own."""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row


def database_url(dbname: str | None = None) -> str:
    url = os.environ.get("DATABASE_URL")
    if url and dbname is None:
        return url
    host = os.environ.get("PGHOST", "127.0.0.1")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")
    name = dbname or os.environ.get("PGDATABASE", "acme_hr")
    auth = f"{user}:{password}@" if password else f"{user}@"
    return f"postgresql://{auth}{host}:{port}/{name}"


def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn
