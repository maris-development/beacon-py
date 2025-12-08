# Getting started

This walkthrough mirrors the public API exposed by the SDK so you can go from zero to a working query in minutes.

## 1. Install and import

Beacon API supports Python 3.10+. Install it from PyPI and import the pieces you need:

```bash
pip install beacon-api
```

```python
from beacon_api import Client
```

!!! note "Editor support"
    The project ships typed stubs (`py.typed`) so VS Code, PyCharm, or notebooks provide signature help and inline documentation out of the box.

## 2. Create a client

Instantiate `Client` with the Beacon base URL and (optionally) headers for authentication. The constructor normalizes headers, sets JSON defaults, and validates connectivity by calling `/api/health`.

```python
client = Client(
    "https://beacon.example.com",
    # jwt_token="<optional bearer token>",
    # proxy_headers={"X-Forwarded-For": "<ip>"},
    # basic_auth=("user", "pass") is also supported
)
```

Use `client.check_status()` to verify connectivity and print the Beacon version, or `client.get_server_info()` to inspect the metadata returned by `/api/info`.

## 3. Discover tables and datasets

`list_tables()` returns a mapping of table names to `DataTable` helpers that already know their description and type.

```python
tables = client.list_tables()
stations = tables["stations-collection"]

print(stations.get_table_description())
schema = stations.get_table_schema()        # Arrow schema with pyarrow fields
schema_arrow = stations.get_table_schema_arrow()
```

If your Beacon Node is running v1.4.0 or later, use `list_datasets()` to enumerate file-backed resources and derive a query directly from a `Dataset`:

```python
datasets = client.list_datasets(pattern="*.parquet", limit=5)
file = datasets["wod/2024-01.parquet"]

print(file.get_file_format(), file.get_file_name())
dataset_schema = file.get_schema()
dataset_query = file.query()
```

!!! tip "Deprecation notice"
    `Client.query()` and `Client.subset()` are still available for backwards compatibility but emit deprecation warnings. Prefer starting from a table (`tables["default"].query()`) or dataset (`file.query()`).

## 4. Build a JSON query

All table and dataset helpers return a `JSONQuery`, a fluent builder with chainable selects and filters:

```python

df = (
    tables['argo'] # Select the 'default' table as our data source
    .query() # Create a new query on the selected table
    .add_select_column("LONGITUDE") # Select the LONGITUDE column
    .add_select_column("LATITUDE") # Select the LATITUDE column
    .add_select_column("JULD")
    .add_select_column("PRES")
    .add_select_column("TEMP")
    .add_select_column("PSAL")
    .add_select_column(".featureType") # Select the .featureType column
    .add_select_column("DATA_TYPE")
    .add_range_filter("JULD", "2020-01-01T00:00:00", "2021-01-01T00:00:00") # Filter for JULD between 2020 and 2021 for the column JULD
    .add_range_filter("PRES", 0, 10) # Filter for pressure between 0 and 10 dbar for the column PRES
    .to_pandas_dataframe() # Execute the query and return the results as a Pandas DataFrame
)
df

```

```python
from datetime import datetime

query = (
    stations
    .query()
    .add_select_columns([
        ("LONGITUDE", None),
        ("LATITUDE", None),
        ("JULD", None),
        ("TEMP", "temperature_c"),
        ("PSAL", "salinity"),
    ])
    .add_select_coalesced(["SEA_NAME", "BASIN"], alias="water_body")
    .add_range_filter("JULD", datetime(2024, 1, 1), datetime(2024, 6, 1))
    .add_range_filter("PRES", 0, 10)
    .add_polygon_filter(
        longitude_column="LONGITUDE",
        latitude_column="LATITUDE",
        polygon=[(-5.2, 52.0), (-5.2, 52.5), (-4.2, 52.5), (-4.2, 52.0), (-5.2, 52.0)],
    )
)
```

Need a quick spatial/temporal subset without writing filters manually? `DataTable.subset()` wraps the same builder and automatically selects longitude/latitude/depth/time columns.

```python
subset_query = stations.subset(
    longitude_column="LONGITUDE",
    latitude_column="LATITUDE",
    time_column="JULD",
    depth_column="PRES",
    columns=["TEMP", "PSAL"],
    bbox=(-20, 40, -10, 50),
    depth_range=(0, 50),
)
```

## 5. Execute the query

Every query inherits rich output helpers from `BaseQuery`:

```python
query = tables['argo'].query()

... # build up the query as shown above

# Serialize results into various formats
df = query.to_pandas_dataframe()
gdf = query.to_geo_pandas_dataframe("LONGITUDE", "LATITUDE")

query.to_parquet("subset.parquet")
query.to_geoparquet("subset.geoparquet", "LONGITUDE", "LATITUDE")
query.to_netcdf("subset.nc")
query.to_nd_netcdf("subset_nd.nc", dimension_columns=["LONGITUDE", "LATITUDE", "JULD"])
query.to_zarr("subset.zarr")
```

!!! note "Beacon compatibility"
    `to_nd_netcdf` requires Beacon Node v1.5.0 or newer.

Need lazy/out-of-core execution? Use `to_dask_dataframe()` or `to_xarray_dataset()` with chunking, or call `to_dask_dataframe().head()` for quick inspection.

!!! info "Profiling and explain"
    Call `query.explain()` to retrieve the Beacon execution plan, or `query.execute()` to inspect the raw HTTP response.

## 6. Running SQL directly

When you already have SQL, skip the builder and call:

```python
sql = client.sql_query("""
    SELECT lon, lat, juld, temperature
    FROM <some-collection-name>
    WHERE juld BETWEEN '2024-01-01T00:00:00' AND '2024-06-30T23:59:59'
""")

df = sql.to_pandas_dataframe()
print(df)
```

## Next steps

- Deep dive into [exploring datasets and tables](using/exploring.md).
- Learn the fluent APIs in [Querying the Beacon Data Lake](using/querying.md).
- Browse the auto-generated [API reference](reference/client.md).
