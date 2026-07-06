"""Shared fixtures for the Beacon API integration test suite.

These tests exercise the ``beacon_api`` package end-to-end against a *running*
Beacon Node. By default they target ``http://localhost:5001`` and the ``default``
table, but both are configurable via environment variables:

    BEACON_TEST_URL     Base URL of the Beacon Node   (default http://localhost:5001)
    BEACON_TEST_TABLE   Table used for query tests     (default "default")

If no node is reachable at ``BEACON_TEST_URL`` the whole suite is skipped rather
than failing, so it is safe to run in environments without a local Beacon.

The fixtures are schema-driven: instead of hard-coding column names they inspect
the live table schema and pick representative columns (longitude/latitude, a
numeric column, a string column, a timestamp column). This keeps the suite
working across different Beacon nodes and datasets.
"""

from __future__ import annotations

import os

import pyarrow as pa
import pytest
import requests

BEACON_URL = os.environ.get("BEACON_TEST_URL", "http://localhost:5001")
TABLE_NAME = os.environ.get("BEACON_TEST_TABLE", "default")
USER_AGENT = "beacon-py-integration-tests/1.0 (ci@maris.nl)"

# The client can resolve discovery (list_tables / describe / list_datasets)
# either through the REST ``/api/*`` endpoints ("rest", the JSON backend) or via
# SQL (``SHOW TABLES`` / ``DESCRIBE`` / ``list_datasets()``). Every server-backed
# test runs under both so the two discovery paths stay in sync.
BACKENDS = ["rest", "sql"]


def _server_reachable(url: str) -> bool:
    """Return True if the Beacon health endpoint responds with 200."""
    try:
        resp = requests.get(url.rstrip("/") + "/api/health", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


# Evaluated once at collection time so we can skip cleanly when there is no node.
SERVER_AVAILABLE = _server_reachable(BEACON_URL)
requires_server = pytest.mark.skipif(
    not SERVER_AVAILABLE,
    reason=f"No Beacon node reachable at {BEACON_URL}",
)


@pytest.fixture(scope="session")
def beacon_url() -> str:
    return BEACON_URL


@pytest.fixture(scope="session")
def table_name() -> str:
    return TABLE_NAME


@pytest.fixture(scope="session", params=BACKENDS)
def backend(request) -> str:
    """Discovery backend under test — parametrized over ``rest`` and ``sql``."""
    return request.param


@pytest.fixture(scope="session")
def client(backend):
    """A connected :class:`beacon_api.Client` for the parametrized backend.

    Skips (rather than fails) the ``sql`` variant on nodes that don't support
    SQL discovery, so the ``rest`` coverage still runs everywhere.
    """
    if not SERVER_AVAILABLE:
        pytest.skip(f"No Beacon node reachable at {BEACON_URL}")
    from beacon_api import Client

    c = Client(BEACON_URL, user_agent=USER_AGENT, backend=backend)
    if backend == "sql":
        try:
            c.sql_query("SHOW TABLES").to_arrow_table()
        except Exception as exc:  # pragma: no cover - depends on node capabilities
            pytest.skip(f"SQL backend not supported on {BEACON_URL}: {exc}")
    return c


@pytest.fixture(scope="session")
def tables(client):
    return client.list_tables()


@pytest.fixture(scope="session")
def default_table(client, tables):
    if TABLE_NAME not in tables:
        pytest.skip(f"Table {TABLE_NAME!r} not present on {BEACON_URL}; found {list(tables)}")
    return tables[TABLE_NAME]


@pytest.fixture(scope="session")
def table_schema(default_table) -> pa.Schema:
    return default_table.get_table_schema_arrow()


def _pick(preferred, pool):
    """First name from ``preferred`` that exists in ``pool``, else pool[0]."""
    for name in preferred:
        if name in pool:
            return name
    return pool[0] if pool else None


@pytest.fixture(scope="session")
def columns(table_schema) -> dict:
    """Representative, distinct columns discovered from the live schema.

    Returns a dict with keys: ``lon``, ``lat``, ``numeric``, ``integer``,
    ``string``, ``timestamp``, plus the full ``floats``/``strings`` lists. Values
    may be ``None`` when the table has no column of that kind.
    """
    floats = [f.name for f in table_schema if pa.types.is_floating(f.type)]
    integers = [f.name for f in table_schema if pa.types.is_integer(f.type)]
    strings = [f.name for f in table_schema if pa.types.is_string(f.type)]
    timestamps = [f.name for f in table_schema if pa.types.is_timestamp(f.type)]

    used: set[str] = set()

    def take(preferred, pool):
        candidates = [c for c in pool if c not in used]
        chosen = _pick(preferred, candidates)
        if chosen is not None:
            used.add(chosen)
        return chosen

    lon = take(["Longitude", "lon", "LONGITUDE", "longitude"], floats)
    lat = take(["Latitude", "lat", "LATITUDE", "latitude"], floats)
    numeric = take(["Depth", "z", "Pressure", "depth"], floats)
    integer = take([], integers)
    string = take(["Cruise", "Station", "LOCAL_CDI_ID"], strings)
    timestamp = take([], timestamps)

    return {
        "lon": lon,
        "lat": lat,
        "numeric": numeric,
        "integer": integer,
        "string": string,
        "timestamp": timestamp,
        "floats": floats,
        "strings": strings,
    }


@pytest.fixture(scope="session")
def select_columns(columns) -> list[str]:
    """A small, safe set of columns to select in query tests."""
    picked = [columns["lon"], columns["lat"], columns["numeric"], columns["string"]]
    return [c for c in picked if c]
