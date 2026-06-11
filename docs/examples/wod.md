# World Ocean Database Example

The World Ocean Database (WOD) is a comprehensive collection of oceanographic data, including temperature, salinity, oxygen, and other parameters. This example demonstrates how to use the `beacon_api` package to query and retrieve data from a Beacon Data Lake that hosts the WOD dataset. The Beacon Data Lake contains around 20 million netCDF files stored into various Beacon Binary Format files (think of a zip containing multiple netcdf files), which are organized into tables for efficient querying.

## Connecting to the Beacon WOD Data Lake

```python
from beacon_api import Client

client = Client(
    "https://beacon-wod.maris.nl",
    user_agent="my-app/1.0 (you@example.com)",
)
tables = client.list_tables()
wod_table = tables['default']
```

## Viewing Table Schema

`get_table_schema_arrow()` returns a `pyarrow.Schema` you can iterate over; `get_table_schema()` returns a plain `{column: python type}` dict.

```python
schema = wod_table.get_table_schema_arrow()
for field in schema:
    print(field.name, field.type)
```

## Querying Data

```python
df = (
    wod_table
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_select_column("z", alias="depth")
    .add_select_column("time")
    .add_select_column("Temperature")
    .add_select_column("Salinity")
    .add_range_filter("time", "2020-01-01T00:00:00", "2021-01-01T00:00:00")
    .to_pandas_dataframe()
)
print(df)
```

## Derived columns for WOD

The `Functions` helper exposes a few transforms tailored to World Ocean Database data. Pass the result to `add_select(...)`:

```python
from beacon_api.query import Functions

df = (
    wod_table
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_select_column("time")
    .add_select_column("Temperature")
    # Convert pressure (dbar) to depth (m) using TEOS-10, given latitude
    .add_select(Functions.map_pressure_to_depth("Pressure", latitude_column="lat", alias="depth"))
    # Translate WOD quality flags into the SeaDataNet (SDN) scheme
    .add_select(Functions.map_wod_quality_flag_to_sdn_scheme("Temperature_WODflag", alias="temp_qc_sdn"))
    .add_range_filter("time", "2020-01-01T00:00:00", "2021-01-01T00:00:00")
    .to_pandas_dataframe()
)
print(df)
```

!!! note "Column names vary per table"
    The exact source column names (e.g. `Pressure`, `Temperature_WODflag`) depend on the table schema — inspect it with `get_table_schema_arrow()` first. `cast_byte_to_char(arg, alias=...)` is also available for decoding byte-encoded character columns.
