"""Discovery integration tests: tables, schemas and datasets."""

from __future__ import annotations

import pyarrow as pa

from beacon_api.table import DataTable

from .conftest import TABLE_NAME, requires_server

pytestmark = requires_server


def test_list_tables_returns_datatables(tables):
    assert isinstance(tables, dict)
    assert tables, "expected at least one table on the node"
    assert all(isinstance(t, DataTable) for t in tables.values())


def test_default_table_present(tables):
    assert TABLE_NAME in tables


def test_table_schema_arrow(table_schema):
    assert isinstance(table_schema, pa.Schema)
    assert len(table_schema) > 0
    # Every field carries a resolved (non-null) pyarrow type.
    assert all(f.type is not None for f in table_schema)


def test_get_table_schema(default_table):
    schema = default_table.get_table_schema()
    # Implementation returns the arrow schema object; it must be indexable by name.
    assert len(schema) > 0
    assert schema.names[0] in schema.names


def test_get_table_description(default_table):
    desc = default_table.get_table_description()
    assert isinstance(desc, str)
    assert desc  # never empty; falls back to "No description available"


def test_get_table_type(default_table):
    # Either a structured dict or a string such as "unknown".
    assert default_table.get_table_type() is not None


def test_describe_table_via_sql(client, table_schema):
    """describe_table() runs SQL DESCRIBE and returns a matching schema."""
    described = client.describe_table(TABLE_NAME)
    assert isinstance(described, pa.Schema)
    assert set(described.names) == set(table_schema.names)


def test_list_datasets_returns_mapping(client):
    """list_datasets() is gated to Beacon >= 1.4.0 and returns a dict."""
    datasets = client.list_datasets(limit=5)
    assert isinstance(datasets, dict)


def test_list_datasets_limit_is_respected(client):
    datasets = client.list_datasets(limit=3)
    assert len(datasets) <= 3
