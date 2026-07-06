# Beacon Data Lake Python API

Python wrapper for interacting with the [Beacon Data Lake](https://maris-development.github.io/beacon/) API. It discovers tables and datasets, inspects schemas, and ships a composable query builder that streams results straight into Pandas, GeoPandas, xarray, and on-disk formats such as (Geo)Parquet, NetCDF, and Zarr.

The full documentation lives at [https://maris-development.github.io/beacon-py/](https://maris-development.github.io/beacon-py/).

## Installation

```bash
pip install beacon-api
```

Beacon API supports Python 3.10+.

## Quick start — connect

The examples below run against the public **World Ocean Database (WOD)** node at `https://beacon-wod.maris.nl`, so you can paste them straight into a notebook. Always pass a `user_agent` that identifies your application (and ideally a contact) so requests can be attributed on shared/public nodes.

```python
from beacon_api import Client

client = Client(
    "https://beacon-wod.maris.nl",
    user_agent="my-app/1.0 (you@example.com)",
    # jwt_token="<bearer token>",        # for protected nodes
    # basic_auth=("user", "pass"),        # or HTTP basic auth
    # backend="sql",                       # SQL-first discovery (default: "rest")
)

client.check_status()  # probes /api/health and prints the Beacon version
```

### SQL backend (Beacon ≥ 1.7.0)

By default the client discovers tables and datasets through the REST `/api/*`
endpoints. Pass `backend="sql"` to resolve everything through SQL instead —
`list_tables()` runs `SHOW TABLES`, `describe_table()` runs `DESCRIBE <table>`,
and `list_datasets()` uses the `list_datasets()` table function. The returned
objects are the same rich `DataTable`/`Dataset` helpers, so the query builder
keeps working.

```python
client = Client("https://beacon-wod.maris.nl", backend="sql")

tables = client.list_tables()          # SHOW TABLES
schema = client.describe_table("default")  # DESCRIBE default -> pyarrow.Schema
datasets = client.list_datasets()      # SELECT * FROM list_datasets()
```

Tables are managed through SQL DDL — create and drop them with `sql_query`:

```python
client.sql_query("CREATE TABLE IF NOT EXISTS measurements (id BIGINT, value DOUBLE)").to_arrow_table()
client.sql_query("DROP TABLE measurements").to_arrow_table()
```

> **DDL/DML and output formats:** statements such as `CREATE TABLE`, `INSERT`,
> `UPDATE`, and `DELETE` do **not** support custom output formats (Parquet, CSV,
> ODV, NetCDF, …). They only work with the Arrow-based outputs
> `to_pandas_dataframe()`, `to_arrow_table()`, and `to_arrow_stream()`.

## Getting started: SQL

Already have SQL? Run it directly and materialize the result as a DataFrame:

```python
df = client.sql_query(
    """
    SELECT lon, lat, z, time, Temperature, Salinity
    FROM "default"
    WHERE time BETWEEN '2020-01-01T00:00:00' AND '2020-02-01T00:00:00'
    """
).to_pandas_dataframe()

print(df.head())
```

`to_pandas_dataframe()` streams the result as Arrow IPC record batches,
collects them into a single Arrow table, and converts that to pandas (requires
Beacon ≥ 1.5.0). You can also stop at Arrow directly:

```python
query = client.sql_query('SELECT lon, lat, time, Temperature FROM "default" LIMIT 1000')

table = query.to_arrow_table()    # pyarrow.Table (all batches collected)
reader = query.to_arrow_stream()  # pyarrow.RecordBatchStreamReader (batch by batch)
```

## Getting started: JSON query builder

Prefer a fluent, typed builder? Start from a table and chain selects and filters. The builder and SQL paths share the same output helpers (`to_pandas_dataframe()`, `to_parquet()`, …).

```python
tables = client.list_tables()
wod = tables["default"]

df = (
    wod
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_select_column("z", alias="depth")
    .add_select_column("time")
    .add_select_column("Temperature")
    .add_select_column("Salinity")
    .add_range_filter("time", "2020-01-01T00:00:00", "2020-02-01T00:00:00")
    .to_pandas_dataframe()
)

print(df.head())
```

## Going further

### Explore tables & schemas

`list_tables()` returns `DataTable` helpers that already know their description, type, and schema:

```python
tables = client.list_tables()
wod = tables["default"]

print(wod.get_table_description())
schema = wod.get_table_schema_arrow()  # pyarrow.Schema
for field in schema:
    print(field.name, field.type)

# get_table_schema() instead returns a plain dict[str, type]
print(wod.get_table_schema())
```

See [Working with tables](https://maris-development.github.io/beacon-py/using/tables/).

### Datasets — query files directly

On Beacon ≥ 1.4.0, `list_datasets()` surfaces file-backed resources you can query without going through a logical table:

```python
datasets = client.list_datasets(pattern="**/*.parquet", limit=10)
first = next(iter(datasets.values()))

print(first.get_file_name(), first.get_file_format())
df = first.query().add_select_column("lon").add_select_column("lat").to_pandas_dataframe()
```

See [Working with datasets](https://maris-development.github.io/beacon-py/using/datasets/).

### More complex queries

The JSON builder supports range/equality/null/geospatial filters, boolean combinations, distinct, sorting, and a range of output formats:

```python
df = (
    wod
    .query()
    .add_select_column("lon")
    .add_select_column("lat")
    .add_select_column("time")
    .add_select_column("Temperature")
    .add_range_filter("time", "2020-01-01T00:00:00", "2020-06-30T23:59:59")
    .add_range_filter("z", 0, 50)
    .add_is_not_null_filter("Temperature")
    .add_bbox_filter("lon", "lat", bbox=(-20, 40, -10, 55))
    .add_sort("time", ascending=True)
    .to_pandas_dataframe()
)
```

See [Querying the Beacon Data Lake](https://maris-development.github.io/beacon-py/using/querying/) for the full builder reference and export helpers (`to_geo_pandas_dataframe`, `to_parquet`, `to_netcdf`, `to_zarr`, …).

### Streaming large results

For result sets too large to buffer, `sql_query_streaming()` returns a PyArrow [`RecordBatchStreamReader`](https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatchStreamReader.html) (requires Beacon ≥ 1.5.0) that you can consume batch by batch:

```python
reader = client.sql_query_streaming('SELECT lon, lat, z, time, Temperature FROM "default"')
for batch in reader:
    # batch is a pyarrow.RecordBatch
    print(batch.num_rows)
```

## Issues

If you encounter any issues or have feature requests, please report them on the [GitHub Issues page](https://github.com/maris-development/beacon-py/issues).

## Development

This project is under active development. Contributions are welcome!

To generate the typings for the API, run:

```bash
stubgen beacon_api -o .
```

To build the wheel package, run:

```bash
python -m build
```
