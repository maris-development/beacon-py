"""SQL execution integration tests (sql_query / sql_query_streaming)."""

from __future__ import annotations

import pandas as pd
import pyarrow as pa

from .conftest import TABLE_NAME, requires_server

pytestmark = requires_server


def _select_sql(select_columns, limit=5):
    cols = ", ".join(f'"{c}"' for c in select_columns)
    return f'SELECT {cols} FROM "{TABLE_NAME}" LIMIT {limit}'


def test_sql_to_pandas(client, select_columns):
    df = client.sql_query(_select_sql(select_columns)).to_pandas_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert len(df) <= 5
    assert list(df.columns) == select_columns


def test_sql_to_arrow_table(client, select_columns):
    table = client.sql_query(_select_sql(select_columns, limit=3)).to_arrow_table()
    assert isinstance(table, pa.Table)
    assert table.num_rows <= 3
    assert table.num_columns == len(select_columns)


def test_sql_to_arrow_stream(client, select_columns):
    reader = client.sql_query(_select_sql(select_columns, limit=10)).to_arrow_stream()
    assert isinstance(reader, pa.RecordBatchStreamReader)
    rows = sum(batch.num_rows for batch in reader)
    assert rows <= 10


def test_sql_query_streaming(client, select_columns):
    reader = client.sql_query_streaming(_select_sql(select_columns, limit=50))
    assert isinstance(reader, pa.RecordBatchStreamReader)
    batches = list(reader)
    assert all(isinstance(b, pa.RecordBatch) for b in batches)
    assert sum(b.num_rows for b in batches) <= 50


def test_sql_limit_bounds_rowcount(client, select_columns):
    df = client.sql_query(_select_sql(select_columns, limit=7)).to_pandas_dataframe()
    assert len(df) <= 7


def test_sql_count(client):
    table = client.sql_query(f'SELECT COUNT(*) AS n FROM "{TABLE_NAME}"').to_arrow_table()
    assert table.num_rows == 1
    n = table.column("n")[0].as_py()
    assert isinstance(n, int)
    assert n >= 0
