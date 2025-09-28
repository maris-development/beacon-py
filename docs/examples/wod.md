# World Ocean Database Example

The World Ocean Database (WOD) is a comprehensive collection of oceanographic data, including temperature, salinity, oxygen, and other parameters. This example demonstrates how to use the `beacon_api` package to query and retrieve data from a Beacon Data Lake that hosts the WOD dataset. The Beacon Data Lake contains around 20 million netCDF files stored into various Beacon Binary Format files (think of a zip containing multiple netcdf files), which are organized into tables for efficient querying.

## Connecting to the Beacon WOD Data Lake

```python
from beacon_api import Client

client = Client("https://beacon-wod.maris.nl")
tables = client.list_tables()
wod_table = tables['default']
```

## Viewing Table Schema

```python
schema = wod_table.get_table_schema()
print(schema)
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
