# Querying the Beacon Data Lake

The SDK exposes two complementary query builders:

1. `JSONQuery` – a fluent, strongly-typed builder generated from a table or dataset via `.query()`.
2. `SQLQuery` – created through `Client.sql_query("SELECT ...")` when you already have raw SQL.

This page highlights the JSON builder because it reflects the method names living in `beacon_api.query.JSONQuery`.

## Create a JSON query

Start from a table (or dataset) and chain builder calls. You can add selects first, then filters, then any optional clauses such as sort or distinct.

```python
from beacon_api import Client

client = Client("https://beacon.example.com")
stations = client.list_tables()["default"]

query = (
    stations
    .query()
    .add_select_columns([
        ("LONGITUDE", None),
        ("LATITUDE", None),
        ("JULD", None),
        ("TEMP", "temperature_c"),
    ])
    .add_range_filter("JULD", "2024-01-01T00:00:00", "2024-06-30T23:59:59")
)
```

!!! tip "Datasets behave the same"
    Every `Dataset` helper exposes `.query()` too. Whether you start from `tables["default"]` or `client.list_datasets()["/data/foo.parquet"]`, the returned object is the same `JSONQuery` class.

## Selecting columns and expressions

- `add_select_column(column, alias=None)` – add one column at a time.
- `add_select_columns([(column, alias), ...])` – batch add columns.
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

## Inspect the plan

Call `query.explain()` to inspect the Beacon execution plan before spending time/materializing the results. For ad-hoc debugging you can also call `query.execute()` to get the raw `requests.Response` object and inspect headers or bytes.

## Materialize results

Every builder inherits from `BaseQuery`, so all outputs are available regardless of whether you built JSON or SQL:

| Method | Description |
| --- | --- |
| `to_pandas_dataframe()` | Executes the query and returns a Pandas `DataFrame`. |
| `to_geo_pandas_dataframe(lon_col, lat_col, crs="EPSG:4326")` | Builds a `GeoDataFrame` and sets the CRS for you. |
| `to_dask_dataframe(temp_name="temp.parquet")` | Streams results into an in-memory Parquet file and returns a lazy `dask.dataframe`. |
| `to_xarray_dataset(dimension_columns, chunks=None)` | Converts the results into an xarray `Dataset`; handy for multidimensional grids. |
| `to_parquet(path)` / `to_geoparquet(path, lon, lat)` / `to_arrow(path)` / `to_csv(path)` | Writes the streamed response directly to disk in the requested format. |
| `to_netcdf(path)` | Builds a local NetCDF file via Pandas → xarray. |
| `to_nd_netcdf(path, dimension_columns)` | Requests the Beacon server to emit NdNetCDF directly (requires Beacon ≥ 1.5.0). |
| `to_zarr(path)` | Converts the results to xarray and persists them as a Zarr store. |
| `to_odv(Odv(...), path)` | Emits an Ocean Data View export when the server supports it. |

Need SQL instead? Construct an `SQLQuery` via `client.sql_query("SELECT ...")` and call the exact same output helpers—`to_pandas_dataframe()`, `to_parquet()` and friends live on the shared `BaseQuery` class.

With these building blocks you can express everything from quick lookups to production-ready pipelines without leaving Python.
