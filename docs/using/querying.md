# Querying the Beacon Data Lake

In this example, we will demonstrate how to create and execute a query on a specific table in the Beacon Data Lake using the `beacon_api` package.

In this example, we will query the `vessels` table to retrieve information about vessels with a specific name.

```python
from beacon_api import Client

client = Client("https://some-beacon-datalake.com")
tables = client.list_tables()
vessels_table = tables['vessels']
query = (
    vessels_table
    .query()
    .add_select_column("VESSEL_NAME")
    .add_select_column("IMO")
    .add_select_column("CALL_SIGN")
    .add_range_filter("LENGTH", 100, 300)
)
df = query.to_pandas_dataframe()
print(df)
```

## Selecting Columns

You can select specific columns to include in the query results using the `add_select_column` method. This helps to limit the amount of data returned and focus on the relevant information. You can also apply an alias to the selected column using the `alias` parameter. This can be useful for renaming columns in the output.

```python
query = (
    vessels_table
    .query()
    .add_select_column("VESSEL_NAME")
    .add_select_column("IMO", alias="IMO_Number")
    .add_select_column("CALL_SIGN")
)
```

Optionally, you can also coalesce columns.
Coalescing columns allows you to combine multiple columns into one, taking the first non-null value from the specified columns.
You can select a coalesced column using the `add_select_coalesced` method.

```python
query = (
    vessels_table
    .query()
    .add_select_coalesced(["VESSEL_NAME", "VESSEL_ALIAS"], "OUTPUT_VESSEL_NAME")
)
```

!!!warning
    Coalescing columns can only be done on columns of the same data type.
    The resulting column will have the same data type as the input columns.
    If the input columns have different data types, an error will be raised when executing the query.
    Coalescing can sometimes prevent filters from being pushed down to the file index, which can lead to slower queries.

## Applying Filters

You can apply various filters to narrow down the query results. Filters can only be applied to columns that are selected in the query (whenever an alias is used, that alias must be used in the filter).
Here are some examples of different types of filters you can use:

### Range Filters

```python
query = (
    vessels_table
    .query()
    .add_select_column("LENGTH")
    .add_select_column("TIME", alias="TIMESTAMP")
    .add_range_filter("LENGTH", 100, 300)
    .add_range_filter("TIMESTAMP", "2022-01-01T00:00:00Z", "2022-12-31T23:59:59Z")
)
```

### Equal/Not Equal Filters

```python
query = (
    vessels_table
    .query()
    .add_select_column("VESSEL_NAME")
    .add_select_column("IMO")
    .add_equals_filter("VESSEL_NAME", "Some Vessel")
    .add_not_equals_filter("IMO", "1234567")
)
```

### Null/Not Null Filters

```python
query = (
    vessels_table
    .query()
    .add_select_column("VESSEL_NAME")
    .add_select_column("IMO")
    .add_is_null_filter("VESSEL_NAME")
    .add_is_not_null_filter("IMO")
)
```

### Polygon Filters

```python
query = (
    vessels_table
    .query()
    .add_select_column("lon", alias="longitude")
    .add_select_column("lat", alias="latitude")
    .add_polygon_filter("longitude", "latitude", [(-74.0, 40.7), (-73.9, 40.7), (-73.9, 40.8), (-74.0, 40.8), (-74.0, 40.7)])
)
```

## Executing the Query (Output)

Once you have built your query with the desired select columns and filters, you can execute it and retrieve the results using various 'to_*' methods. The most common method is `to_pandas_dataframe`, which returns the results as a Pandas DataFrame.

### To Pandas DataFrame

```python
df = (
    query
    .select_column("VESSEL_NAME")
    .select_column("IMO")
    .to_pandas_dataframe()
)
print(df)
```

### To GeoPandas DataFrame

!!!note 
    GeoPandas support requires the `geopandas` extra dependency. You can install it using:
    ```bash
    pip install beacon_api[geopandas]
    ```

```python
gdf = (
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_geopandas_dataframe("LONGITUDE", "LATITUDE")
)
print(gdf)
```

### To Parquet File

```python
(
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_parquet("vessels.parquet")
)
```

### To GeoParquet File

```python
(
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_geoparquet("vessels.geoparquet", "LONGITUDE", "LATITUDE")
)
```

### To Arrow Ipc File

```python
(
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_arrow("vessels.arrow")
)
```

### To NetCDF File

```python
(
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_netcdf("vessels.nc")
)
```

### To CSV File

```python
(
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_csv("vessels.csv")
)
```

### To Zarr Store

!!!note 
    Zarr support requires the `zarr` extra dependency. You can install it using:
    ```bash
    pip install beacon_api[zarr]
    ```

```python
(
    query
    .select_column("VESSEL_NAME")
    .select_column("LONGITUDE")
    .select_column("LATITUDE")
    .to_zarr("vessels.zarr")
)
```
