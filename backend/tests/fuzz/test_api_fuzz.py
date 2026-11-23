"""Schema-driven API fuzzing with Schemathesis.

Every operation in the OpenAPI schema gets generated requests, valid and
invalid. Each response is checked: no 5xx, the status code is one the schema
documents, and the body matches the documented response model. The app runs
in-process against the per-worker test database, inside a transaction that is
rolled back, so a fuzz run leaves no rows behind.

Budget: FUZZ_EXAMPLES (default 25 per operation); the nightly job raises it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
import schemathesis
from app.db import get_conn
from app.main import app
from hypothesis import HealthCheck, settings
from schemathesis.checks import positive_data_acceptance

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

# JSON Schema cannot say "end_date is on or after start_date", so a request can
# fit the schema and still get a 422. Only these operations are excused from the
# "schema-valid requests are accepted" check; every other check still runs.
CROSS_FIELD_RULES = {"POST /leave-requests"}

pytestmark = pytest.mark.db


@pytest.fixture
def wired_app(conn: psycopg.Connection) -> Iterator[None]:
    app.dependency_overrides[get_conn] = lambda: conn
    yield
    app.dependency_overrides.clear()


@schema.parametrize()
@settings(
    max_examples=int(os.environ.get("FUZZ_EXAMPLES", "25")),
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_api_conforms_to_its_schema(case: schemathesis.Case, wired_app: None) -> None:
    excluded = []
    if case.operation.label in CROSS_FIELD_RULES:
        excluded.append(positive_data_acceptance)
    case.call_and_validate(excluded_checks=excluded)
