# Querying the Beacon Data Lake

The SDK exposes two complementary query builders:

1. `JSONQuery` – a fluent, strongly-typed builder generated from a table or dataset via `.query()`.
2. `SQLQuery` – created through `Client.sql_query("SELECT ...")` when you already have raw SQL.

This page highlights the JSON builder because it reflects the method names living in `beacon_api.query.JSONQuery`.

## Create a JSON query

Start from a table (or dataset) and chain builder calls. You can add selects first, then filters, then any optional clauses such as sort or distinct.

```python
from beacon_api import Client

client = Client(
    "https://beacon-wod.maris.nl",
    user_agent="my-app/1.0 (you@example.com)",
)
stations = client.list_tables()["default"]

query = (
    stations
    .query()
    .add_select_column("LONGITUDE")
    .add_select_column("LATITUDE")
    .add_select_column("JULD")
    .add_select_column("TEMP", alias="temperature_c")
    .add_range_filter("JULD", "2024-01-01T00:00:00", "2024-06-30T23:59:59")
)
```

!!! tip "Datasets behave the same"
    Every `Dataset` helper exposes `.query()` too. Whether you start from `tables["default"]` or `client.list_datasets()["/data/foo.parquet"]`, the returned object is the same `JSONQuery` class.

## Selecting columns and expressions

- `add_select_column(column, alias=None)` – add one column at a time (call repeatedly to build your projection).
- `add_select_coalesced(["col_a", "col_b"], alias="preferred")` – build a COALESCE expression server-side.
- `add_selects([...])` – append fully-specified `Select` nodes when you need lower-level control.

You can also use helpers from `beacon_api.query.Functions` to derive columns. For example, concatenate voyage identifiers or cast a numeric field:

```python
from beacon_api.query import Functions

query = (
    query
    .add_select(Functions.concat(["CRUISE", "STATION"], alias="cast_id"))
    .add_select(Functions.try_cast_to_type("TEMP", to_type="float64", alias="temp_float"))
)
```

!!! warning
    Make sure the columns you reference in filters are also present in the select list. When you rename a column via `alias`, use that alias in your filters.

## Adding filters

JSON queries support the same filter primitives as the Beacon API:

```python
filtered = (
    query
    .add_equals_filter("DATA_TYPE", "CTD")
    .add_not_equals_filter("VESSEL", "TEST")
    .add_range_filter("PRES", 0, 10)
    .add_is_not_null_filter("TEMP")
    .add_bbox_filter("LONGITUDE", "LATITUDE", bbox=(-20, 40, -10, 55))
)
```

For custom boolean logic you can compose `AndFilter`/`OrFilter` nodes manually and pass them to `add_filter()`:

```python
from beacon_api.query import AndFilter, RangeFilter

filtered = filtered.add_filter(
    AndFilter([
        RangeFilter("TEMP", gt_eq=-2, lt_eq=35),
        RangeFilter("PSAL", gt_eq=30, lt_eq=40),
    ])
)
```

Geospatial workflows are covered via `add_polygon_filter(longitude_column, latitude_column, polygon)` which accepts any closed polygon expressed as a list of `(lon, lat)` tuples.

## Distinct and sorting

Use `set_distinct(["COLUMN"])` to deduplicate rows before export. Sorting is handled per column:

```python
query = (
    query
    .set_distinct(["CRUISE", "STATION"])
    .add_sort("JULD", ascending=True)
    .add_sort("DEPTH", ascending=False)
)
```

## Pagination and limiting rows

Use `set_limit(n)` to cap how many rows come back, and `set_offset(n)` to skip rows — together they page through a large result set:

```python
# First 1,000 rows
page_one = query.set_limit(1000).set_offset(0)

# Next 1,000 rows
page_two = query.set_limit(1000).set_offset(1000)
```

`set_limit` on its own is also a quick way to preview a query before materializing the full result.

## Inspect the plan

Call `query.explain()` to inspect the Beacon execution plan before spending time/materializing the results. For ad-hoc debugging you can also call `query.execute()` to get the raw `requests.Response` object and inspect headers or bytes.

## Materialize results

Every builder inherits from `BaseQuery`, so all outputs are available regardless of whether you built JSON or SQL:

| Method | Description |
| --- | --- |
| `to_pandas_dataframe()` | Streams the result as Arrow record batches, collects them into one Arrow table, and converts to a Pandas `DataFrame` (requires Beacon ≥ 1.5.0). |
| `to_arrow_table()` | Streams and collects every batch into a single PyArrow `Table`. |
| `to_arrow_stream()` | Returns a PyArrow `RecordBatchStreamReader` so you can consume large results batch by batch (requires Beacon ≥ 1.5.0). |
| `to_geo_pandas_dataframe(lon_col, lat_col, crs="EPSG:4326")` | Builds a `GeoDataFrame` and sets the CRS for you. |
| `execute_streaming()` | Lower-level alias of `to_arrow_stream()`. |
| `to_xarray_dataset(dimension_columns, chunks=None)` | Converts the results into an xarray `Dataset`; handy for multidimensional grids. |
| `to_parquet(path)` / `to_geoparquet(path, lon, lat)` / `to_arrow(path)` / `to_csv(path)` | Writes the streamed response directly to disk in the requested format. |
| `to_netcdf(path)` | Builds a local NetCDF file via Pandas → xarray. |
| `to_nd_netcdf(path, dimension_columns)` | Requests the Beacon server to emit NdNetCDF directly (requires Beacon ≥ 1.5.0). |
| `to_zarr(path)` | Converts the results to xarray and persists them as a Zarr store. |
| `to_odv(Odv(...), path)` | Emits an Ocean Data View export when the server supports it. |

!!! warning "DDL/DML statements only support Arrow outputs"
    SQL statements that change the catalog or data — `CREATE TABLE`, `INSERT`,
    `UPDATE`, `DELETE`, `DROP TABLE`, … — do **not** support the custom file
    output formats. Only `to_pandas_dataframe()`, `to_arrow_table()`, and
    `to_arrow_stream()` work for them; calling `to_parquet()`, `to_csv()`,
    `to_odv()` and friends on a DDL/DML statement will fail.

## Managing tables with SQL

On Beacon ≥ 1.7.0 tables are created and dropped through SQL DDL rather than the
deprecated REST admin helpers. Run the statement through `sql_query` and collect
it with one of the Arrow outputs:

```python
client.sql_query(
    "CREATE TABLE IF NOT EXISTS measurements (id BIGINT, name VARCHAR, value DOUBLE)"
).to_arrow_table()

# Populate from a query
client.sql_query(
    "INSERT INTO measurements SELECT id, name, value FROM staging"
).to_arrow_table()

client.sql_query("DROP TABLE measurements").to_arrow_table()
```

## Example gallery

### Streaming large results

When a result set is too large to buffer in memory, call `execute_streaming()` instead of a `to_*` helper. It returns a PyArrow `RecordBatchStreamReader` (requires Beacon ≥ 1.5.0) that you can iterate batch by batch — works the same whether you start from a table or a `Dataset`.

```python
datasets = client.list_datasets(pattern="**/*.parquet", limit=1)
dataset = next(iter(datasets.values()))

reader = (
    dataset
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_select_column("time")
    .add_select_column("temperature")
    .add_range_filter("time", "2023-01-01T00:00:00", "2023-12-31T23:59:59")
    .execute_streaming()
)

for batch in reader:
    # batch is a pyarrow.RecordBatch — process it without loading everything at once
    print(batch.num_rows)

# ...or collect everything into one Arrow Table / DataFrame
# table = reader.read_all(); df = table.to_pandas()
```

The same stream is available straight from SQL via `client.sql_query_streaming("SELECT ...")`.

### SQL equivalent

Prefer SQL? Build once in SQL, then call the same output helpers.

```python
sql = client.sql_query(
    """
    SELECT LONGITUDE, LATITUDE, JULD, TEMP AS temperature_c
    FROM argo
    WHERE DATA_TYPE = 'CTD'
      AND JULD BETWEEN '2024-01-01 00:00:00'
                    AND '2024-06-30 23:59:59'
      AND PRES BETWEEN 0 AND 50
    ORDER BY JULD ASC
    """
)

sql.to_parquet("ctd_slice.parquet")
```

## Pandas-first examples

The snippets below all end with `to_pandas_dataframe()` so you can copy them straight into notebooks.

### Custom column selection + range filters

```python
tables = client.list_tables()
collection = tables["default"]

df = (
    collection
    .query()
    .add_select_column("CRUISE")
    .add_select_column("STATION")
    .add_select_column("JULD")
    .add_select_column("TEMP", alias="temperature_c")
    .add_range_filter("JULD", "2024-01-01T00:00:00", "2024-03-01T00:00:00")
    .add_range_filter("PRES", 0, 20)
    .to_pandas_dataframe()
)
```

### Distinct voyages with equality filters

```python
voyages = (
    collection
    .query()
    .add_select_column("CRUISE")
    .add_select_column("STATION")
    .add_select_column("DATA_TYPE")
    .add_equals_filter("DATA_TYPE", "PROFILER")
    .set_distinct(["CRUISE", "STATION", "DATA_TYPE"])
    .to_pandas_dataframe()
)
```

### Sorted subset with boolean combinations

```python
from beacon_api.query import OrFilter, AndFilter, RangeFilter

sorted_subset = (
    collection
    .query()
    .add_select_column("LONGITUDE")
    .add_select_column("LATITUDE")
    .add_select_column("JULD")
    .add_select_column("TEMP")
    .add_select_column("PSAL")
    .add_filter(
        OrFilter([
            AndFilter([
                RangeFilter("JULD", gt_eq="2024-01-01T00:00:00", lt_eq="2024-02-01T00:00:00"),
                RangeFilter("PRES", lt_eq=10),
            ]),
            AndFilter([
                RangeFilter("JULD", gt_eq="2024-05-01T00:00:00", lt_eq="2024-06-01T00:00:00"),
                RangeFilter("PRES", lt_eq=5),
            ]),
        ])
    )
    .add_is_not_null_filter("TEMP")
    .add_sort("JULD", ascending=True)
    .add_sort("PRES", ascending=True)
    .to_pandas_dataframe()
)
```

### Combining coalesced columns with polygon filters

```python
from beacon_api.query import Functions

regions = (
    collection
    .query()
    .add_select_column("LONGITUDE")
    .add_select_column("LATITUDE")
    .add_select_column("JULD")
    .add_select(Functions.coalesce(["SEA_NAME", "BASIN"], alias="region"))
    .add_polygon_filter(
        longitude_column="LONGITUDE",
        latitude_column="LATITUDE",
        polygon=[(-5.5, 51.5), (-4.0, 51.5), (-4.0, 52.5), (-5.5, 52.5), (-5.5, 51.5)],
    )
    .set_distinct(["region"])
    .to_pandas_dataframe()
)
```

Need SQL instead? Construct an `SQLQuery` via `client.sql_query("SELECT ...")` and call the exact same output helpers—`to_pandas_dataframe()`, `to_parquet()` and friends live on the shared `BaseQuery` class.

With these building blocks you can express everything from quick lookups to production-ready pipelines without leaving Python.
