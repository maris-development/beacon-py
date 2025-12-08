# Exploring the Beacon Data Lake

This guide shows how to inspect/query a Beacon Node, discover the available data, and subset slices for local analysis. All snippets are built directly on top of the public SDK classes so you can paste them into scripts or notebooks as-is.

## Connect and verify

```python
from beacon_api import Client

client = Client("https://beacon.example.com")
client.check_status()  # probes /api/health and prints the version

info = client.get_server_info()
print(info["beacon_version"], info.get("extensions"))
```

!!! tip "Troubleshooting connectivity"
    The client automatically prefixes relative URLs with the base URL. If you see `Failed to connect to server`, double-check the base URL and whether your token grants access to `/api/health`.

## Discover tables

`list_tables()` returns a mapping of table names to `DataTable` helpers with cached metadata. Iterate to learn what each collection represents:

```python
tables = client.list_tables()
for name, table in tables.items():
    print(f"{name} → {table.get_table_type()} :: {table.get_table_description()}")
```

Grab one table—`default` exists on every Beacon deployment—and inspect its schema:

```python
default_table = tables["default"]

schema_arrow = default_table.get_table_schema_arrow()
for field in schema_arrow:
    print(f"{field.name}: {field.type}")
```

Use `get_table_schema()` when you want a PyArrow `Schema` object you can re-use (for instance, to validate a DataFrame before upload).

## Sample data quickly

Need a glance at the data without hand-writing longitude/latitude filters? `DataTable.subset()` configures a `JSONQuery` with a bounding box, depth range, and time window:

```python
sample = default_table.subset(
    longitude_column="LONGITUDE",
    latitude_column="LATITUDE",
    time_column="JULD",
    depth_column="PRES",
    columns=["TEMP", "PSAL"],
    bbox=(-20, 40, -10, 50),
    depth_range=(0, 25),
)

preview = sample.to_pandas_dataframe().head()
```

Because `subset()` returns a normal `JSONQuery`, you can tack on additional selects/filters before executing it.

## Browse individual datasets (Beacon ≥ 1.4)

When the Beacon Node exposes `/api/list-datasets`, you can work with files directly instead of logical tables:

```python
datasets = client.list_datasets(pattern="**/*.parquet", limit=10)
first_file = next(iter(datasets.values()))

print(first_file.get_file_path(), first_file.get_file_format())
dataset_schema = first_file.get_schema()
```

Once you have a `Dataset`, spin up a query exactly the same way as with tables:

```python
dataset_query = first_file.query()
dataset_df = (
    dataset_query
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_range_filter("time", "2023-01-01T00:00:00", "2023-12-31T23:59:59")
    .to_pandas_dataframe()
)
```

## Go deeper with explain and export helpers

- `query.explain()` calls `/api/explain-query` so you can see exactly how the Beacon Node plans to execute the request.
- `query.to_geo_pandas_dataframe(longitude, latitude)` materializes a `GeoDataFrame` complete with CRS.
- `query.to_xarray_dataset(["JULD", "PRES"])` yields an n-dimensional dataset perfect for scientific workflows.
- `query.to_parquet("subset.parquet")`, `query.to_nd_netcdf("subset_nd.nc", ["JULD", "DEPTH"])`, or `query.to_zarr("subset.zarr")` stream results directly to disk.

With these building blocks you can confidently explore any Beacon Data Lake, whether you prefer notebooks, scripts, or dashboards.
