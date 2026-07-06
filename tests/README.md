# Integration test suite

These tests exercise `beacon_api` end-to-end against a **running Beacon Node**.

## Running

```bash
pip install -e ".[test]"
pytest                      # runs everything in tests/
```

By default the suite targets `http://localhost:5001` and the `default` table.
Override with environment variables:

| Variable            | Default                  | Purpose                        |
| ------------------- | ------------------------ | ------------------------------ |
| `BEACON_TEST_URL`   | `http://localhost:5001`  | Base URL of the Beacon Node    |
| `BEACON_TEST_TABLE` | `default`                | Table used for query tests     |

```bash
BEACON_TEST_URL=https://beacon-wod.maris.nl BEACON_TEST_TABLE=default pytest
```

If no node is reachable at `BEACON_TEST_URL`, the integration tests are
**skipped** (not failed). The offline serialization tests in
`test_query_compile.py` always run.

## Layout

| File                    | Covers                                                        |
| ----------------------- | ------------------------------------------------------------- |
| `conftest.py`           | Shared fixtures; discovers representative columns from schema |
| `test_connection.py`    | Client construction, status, server info, auth validation     |
| `test_discovery.py`     | `list_tables`, schema helpers, `describe_table`, datasets     |
| `test_backends.py`      | REST vs SQL wiring and cross-backend agreement                |
| `test_sql.py`           | `sql_query` / `sql_query_streaming` → pandas / Arrow / stream |
| `test_json_query.py`    | JSON builder: selects, filters, sort, distinct, limit/offset  |
| `test_outputs.py`       | Export helpers: parquet, csv, arrow, geoparquet, netcdf, zarr |
| `test_query_compile.py` | Offline — the exact JSON request body the builder produces    |

## Backends

The client resolves discovery through either the REST `/api/*` endpoints
(`backend="rest"`, the JSON backend) or SQL (`backend="sql"` — `SHOW TABLES`,
`DESCRIBE`, `list_datasets()`). The `backend` fixture in `conftest.py` is
**parametrized over both**, so every server-backed test runs twice and shows up
as `…[rest]` / `…[sql]`. The `sql` variant self-skips on nodes that don't
support SQL discovery. Export tests (`test_outputs.py`) are pinned to `rest`
since output formatting is backend-independent.

## Known findings (xfail)

Two real defects are recorded as `xfail` so the suite stays green while
documenting them:

- **`add_sort` on a mixed-case column** — `SortColumn.to_dict()` emits the
  column unquoted, the node lower-cases the identifier and fails. Quoting it
  (`{"Asc": "\"Depth\""}`) works.
- **`geoparquet` output** — crashes the Beacon node (connection reset) on every
  request; affects `to_geoparquet` and `to_geo_pandas_dataframe`.

The fixtures are **schema-driven**: rather than hard-coding column names they
inspect the live table schema and pick a longitude/latitude, a numeric, a
string and a timestamp column. Tests `skip` cleanly when the table lacks a
column of the kind they need, so the suite adapts to different nodes.
