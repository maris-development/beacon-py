# Beacon API Python SDK

The Beacon Python SDK is a client for Beacon Data Lakes. It discovers datasets, inspects schemas, and ships a composable query builder that can stream results into familiar scientific Python tools.

## Why use the SDK?

- **One client for every Beacon Node** – the `Client` wires authentication headers, probes `/api/health`, and exposes helpers such as `list_tables()` and `list_datasets()`.
- **Discoverability built-in** – `DataTable` and `Dataset` helpers return Arrow schemas, table descriptions, and file metadata so you always know which columns exist before writing a query.
- **Chainable JSON/SQL query builders** – start from a table or dataset, add selects, filters, distinct clauses, or geospatial predicates, and export to Pandas, GeoPandas, xarray, a streaming PyArrow reader, or on-disk formats such as (Geo)Parquet, Arrow IPC, NetCDF, NdNetCDF, CSV, Zarr, or ODV.
- **Typed, well-documented API surface** – the docs you are reading mirror the public classes (`Client`, `DataTable`, `Dataset`, `JSONQuery`, `SQLQuery`, …) so editors and notebooks surface the same guidance.

!!! note "Beacon Data Lake platform"
    Looking for the platform documentation itself? Head over to the [Beacon Data Lake docs](https://maris-development.github.io/beacon/).

## Quick start

The snippet below runs against the public **World Ocean Database (WOD)** node, so you can paste it straight into a notebook. Always pass a `user_agent` that identifies your application.

```python
from beacon_api import Client

client = Client(
    "https://beacon-wod.maris.nl",
    user_agent="my-app/1.0 (you@example.com)",
    # jwt_token="<optional bearer token>",  # for protected nodes
)

client.check_status()  # probes /api/health and prints the Beacon version

tables = client.list_tables()
wod = tables["default"]

df = (
    wod
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_select_column("time")
    .add_select_column("Temperature")
    .add_range_filter("time", "2020-01-01T00:00:00", "2020-12-31T23:59:59")
    .to_pandas_dataframe()
)
```

## Core concepts

### Client

Manages the HTTP session, authentication headers, and compatibility checks. Use `get_server_info()` to inspect the Beacon version and extensions, `list_tables()` to enumerate logical collections, or `list_datasets()` (Beacon ≥ 1.4.0) to work with direct file paths. Pass `backend="sql"` (Beacon ≥ 1.7.0) to resolve discovery through SQL (`SHOW TABLES`, `DESCRIBE`, `list_datasets()`) instead of the REST `/api/*` endpoints; `describe_table()` returns a `pyarrow.Schema`.

### Tables and datasets

Tables (instances of `DataTable`) represent logical collections backed by one or more datasets. They expose helpers such as `get_table_schema()` or `subset()` to quickly explore spatial/temporal windows. Datasets expose similar helpers but start from a known file/URI and can construct a query via `Dataset.query()`.

### Query builders

`JSONQuery` powers the fluent builder: select columns, coalesce values, add range/equality/geospatial filters, sorting, distinct clauses, or call `explain()` to see the server-side plan. Prefer `Client.sql_query()` when you already have SQL.

### Rich outputs

Every query inherits the `BaseQuery` output helpers. Materialize into `to_pandas_dataframe()` (which streams and collects Arrow batches), `to_arrow_table()`, `to_geo_pandas_dataframe()`, or `to_xarray_dataset()`, stream large results lazily with `to_arrow_stream()` (a PyArrow `RecordBatchStreamReader`), or write datasets using `to_parquet()`, `to_nd_netcdf()`, `to_zarr()`, `to_odv()` and more. SQL DDL/DML statements only support the Arrow-based outputs.

## Where to next?

- [Installation](installation.md) – supported Python versions and optional extras.
- [Getting started](getting_started.md) – end-to-end walkthrough from connecting a client to exporting a DataFrame.
- [Using Beacon](using/exploring.md) – deep dives into tables, datasets, and the JSON query builder.
- [Working with datasets](using/datasets.md) – jump straight from file paths/URIs to a query builder.
- [API reference](reference/client.md) – auto-generated API docs straight from the SDK source.
