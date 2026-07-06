"""Backend-specific tests: REST ("json") vs SQL discovery.

Most of the suite already runs under *both* backends via the parametrized
``client`` fixture (see ``conftest.py``). These tests add checks that are
specifically about the backend wiring and about the two discovery paths
agreeing with each other.
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from beacon_api import Client

from .conftest import BEACON_URL, SERVER_AVAILABLE, TABLE_NAME, USER_AGENT, requires_server


def _make_client(backend: str) -> Client:
    """Construct a client for ``backend``, skipping if the node can't serve it."""
    if not SERVER_AVAILABLE:
        pytest.skip(f"No Beacon node reachable at {BEACON_URL}")
    client = Client(BEACON_URL, user_agent=USER_AGENT, backend=backend)
    if backend == "sql":
        try:
            client.sql_query("SHOW TABLES").to_arrow_table()
        except Exception as exc:  # pragma: no cover - depends on node capabilities
            pytest.skip(f"SQL backend not supported on {BEACON_URL}: {exc}")
    return client


# --- Wiring: the parametrized client reports the requested backend ---------


@requires_server
def test_client_reports_backend(client, backend):
    assert client.session.backend == backend


@requires_server
def test_discovery_runs_under_backend(default_table, table_schema):
    """The parametrized fixtures produce a usable table + schema per backend."""
    assert default_table.table_name == TABLE_NAME
    assert isinstance(table_schema, pa.Schema)
    assert len(table_schema) > 0


# --- Cross-backend agreement (constructs both clients directly) ------------


@requires_server
def test_both_backends_discover_default():
    rest_tables = _make_client("rest").list_tables()
    sql_tables = _make_client("sql").list_tables()
    assert TABLE_NAME in rest_tables
    assert TABLE_NAME in sql_tables


@requires_server
def test_schemas_agree_across_backends():
    """REST /api/table-schema and SQL DESCRIBE resolve the same columns."""
    rest = _make_client("rest").list_tables()[TABLE_NAME]
    sql = _make_client("sql").list_tables()[TABLE_NAME]

    rest_schema = rest.get_table_schema_arrow()
    sql_schema = sql.get_table_schema_arrow()

    assert set(rest_schema.names) == set(sql_schema.names)
    # Types should agree column-for-column, too.
    rest_types = {f.name: f.type for f in rest_schema}
    sql_types = {f.name: f.type for f in sql_schema}
    assert rest_types == sql_types


@requires_server
def test_list_datasets_both_backends():
    rest_ds = _make_client("rest").list_datasets(limit=5)
    sql_ds = _make_client("sql").list_datasets(limit=5)
    assert isinstance(rest_ds, dict)
    assert isinstance(sql_ds, dict)


@requires_server
def test_query_from_sql_discovered_table():
    """A table discovered via SQL still executes a JSON query."""
    table = _make_client("sql").list_tables()[TABLE_NAME]
    schema = table.get_table_schema_arrow()
    col = schema.names[0]
    df = table.query().add_select_column(col).set_limit(3).to_pandas_dataframe()
    assert list(df.columns) == [col]
    assert len(df) <= 3
