# Working with datasets

Sometimes you already know the precise file or object store path you want to analyze. Instead of going through a logical table, you can treat that file as a `Dataset` and issue a JSON query directly against it.

## Enumerate datasets (Beacon ≥ 1.4.0)

`Client.list_datasets()` calls `/api/list-datasets` and returns a dictionary of `Dataset` helpers keyed by their `file_path`:

```python
from beacon_api import Client

client = Client(
    "https://beacon-wod.maris.nl",
    user_agent="my-app/1.0 (you@example.com)",
)
raw_datasets = client.list_datasets(pattern="**/*.parquet", limit=20)
print(f"Discovered {len(raw_datasets)} eligible files")
```

Each value in the dictionary is a `Dataset` instance.

!!! note "SQL backend"
    When the client is created with `backend="sql"`, `list_datasets()` queries the
    `list_datasets()` SQL table function (`SELECT * FROM list_datasets()`) instead
    of `/api/list-datasets`. `limit`/`offset` are pushed into the SQL statement and
    the `pattern` glob is applied client-side. The returned values are still
    `Dataset` instances.

```python
first = next(iter(raw_datasets.values()))
print(first.get_file_format(), first.get_file_name())
print(first.get_file_path())
```

## Inspect schema

`Dataset.get_schema()` makes the same `pyarrow.Schema` request that tables use, but it is scoped to the exact file you selected:

```python
schema = first.get_schema()
for field in schema:
    print(field.name, field.type)
```

On the `sql` backend this is resolved via the `read_schema([...], '<format>')`
table function instead of `/api/dataset-schema`.

Use this information to decide which columns to select before running a heavy query.

## Build a query from a dataset

Every `Dataset` exposes `.query()` which returns the familiar `JSONQuery` builder:

```python
dataset_query = (
    first
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_range_filter("time", "2024-01-01T00:00:00", "2024-06-30T23:59:59")
)

subset = dataset_query.to_pandas_dataframe()
```

The method understands a couple of format-specific options:

- CSV datasets accept `delimiter=","` (or any other single-character delimiter).
- Zarr datasets accept `statistics_columns=["col_a", "col_b"]` so you can hint which axes include statistics.

Pass these keyword arguments directly to `.query()`:

```python
csv_file = client.list_datasets(pattern="*.csv")["raw.csv"]
query = csv_file.query(delimiter=";")
```

```python
zarr_file = client.list_datasets(pattern="*/zarr.json")["profiles.zarr/zarr.json"]
query = zarr_file.query(statistics_columns=["time", "depth"])
```

Everything else—selects, filters, sorts, exports—matches the `DataTable` workflow outlined in the [query guide](querying.md). Datasets simply skip the logical abstraction layer when you want to target files directly.
