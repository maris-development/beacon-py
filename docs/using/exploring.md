# Exploring the Beacon Data Lake

In this section, we will explore the capabilities of the Beacon Data Lake by performing some common tasks.

## Connecting to a Beacon Data Lake

First, we need to connect to a Beacon Data Lake using the `beacon_api` package:

```py
from beacon_api import Client
client = Client("https://beacon.example.com")
```

## Listing Available Tables

First, let's list all available tables in the Beacon Data Lake:

```py
tables = client.list_tables()
print(tables)
```

## Viewing Table Schema

Next, we can view the schema of a specific table to understand its structure and available columns:

```py
schema = tables['default'].get_table_schema()
print(schema)
```

## Querying Data

Finally, we can perform a query on the data:

```py
df = (
    tables['default']
    .query()
    .add_select_column("LONGITUDE")
    .add_select_column("LATITUDE")
    .add_select_column("JULD")
    .add_range_filter("JULD", "2020-01-01T00:00:00", "2021-01-01T00:00:00")
    .to_pandas_dataframe()
)
print(df)
```
