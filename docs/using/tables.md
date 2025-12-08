# Working with tables

Beacon tables (also called *data collections*) are exposed as instances of `beacon_api.table.DataTable`. They wrap server metadata so you can quickly describe the content of a table before running costly queries.

## Fetch a table

```python
tables = client.list_tables()
stations = tables["stations-collection"]

print(stations.table_name)
```

`list_tables()` returns a dictionary, so simply index into it using the table name you are interested in.

## Metadata helpers

Every `DataTable` fetches `/api/table-config?table_name=...` during initialization. Access that metadata via:

```python
stations.get_table_description()
stations.get_table_type()
```

Use `get_table_schema_arrow()` or `get_table_schema()` to inspect the schema before building a query:

```python
schema = stations.get_table_schema_arrow()
print(schema)

# convert to a dict of {column_name: python_type}
schema_dict = stations.get_table_schema()
```

The schema result is a PyArrow `Schema`, meaning you can introspect field metadata, dtypes, or reuse it when constructing downstream DataFrames.

## Create a query from a table

Once you know which columns you need, call `stations.query()` to obtain a `JSONQuery` builder:

```python
query = (
    stations
    .query()
    .add_select_column("LONGITUDE")
    .add_select_column("LATITUDE")
    .add_select_column("JULD")
    .add_range_filter("JULD", "2024-01-01T00:00:00", "2024-03-01T00:00:00")
)

df = query.to_pandas_dataframe()
```

Because `JSONQuery` is fluent, you can keep chaining selects, filters, sorting, or distinct clauses before materializing the results. Refer to [Querying the Beacon Data Lake](querying.md) for every available builder method.

## Subset convenience helper

For spatial/temporal slices there is `DataTable.subset()`. It adds the longitude, latitude, depth, and time selections plus the appropriate filters for you:

```python
from datetime import datetime

subset = stations.subset(
    longitude_column="LONGITUDE",
    latitude_column="LATITUDE",
    time_column="JULD",
    depth_column="PRES",
    columns=["TEMP", "PSAL", ".featureType"],
    bbox=(-20, 40, -10, 55),
    depth_range=(0, 50),
    time_range=(datetime(2024, 1, 1), datetime(2024, 6, 1)),
)

subset_df = subset.to_pandas_dataframe()
```

Because `subset()` simply returns a `JSONQuery`, you can continue chaining methods—for example, add equals filters or change the output format with `subset.to_geoparquet(...)`.
