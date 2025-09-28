# Getting Started

To get started with the `beacon_api` package, follow these steps:

### Install the package using pip

   ```bash
   pip install beacon_api
   ```

### Import the package in your Python code

   ```py
   import beacon_api
   ```

!!!note "Code Completion"
    The package integrates well with VS Code and PyCharm, providing features like code completion and inline documentation.
    It will also work in Jupyter Notebooks but may not provide the same level of code completion.

### Connect to a Beacon Data Lake

   ```py
   client = beacon_api.Client("https://some-beacon-datalake.com")
   ```

!!! tip "Passing API Token"
    If your Beacon Data Lake requires authentication, you can pass an API token when creating the client:
    ```py
    client = beacon_api.Client("https://some-beacon-datalake.com", jwt_token="your_api_token")
    ```

### List available tables

To view all the available tables/data collections in the connected Beacon Data Lake, you can use the `list_tables` method:

```py
tables = client.list_tables()
print(tables)
```

!!!note
    The `list_tables` method returns a dictionary where the keys are the table names and the values are `Table` objects that you can use to interact with each table.

### Viewing the schema (available columns) of a specific table

To view the schema (available columns) of a specific table, you can use the `get_table_schema` method:

```py
tables = client.list_tables()
schema = tables['default'].get_table_schema()
print(schema)   
```

!!!note
    Every beacon will have a table named `default`. This can be used to query the main data collection of the beacon.

### Create and execute a query

To create and execute a query on a specific table, you can use the `query` method of the `Table` object. Here's an example of how to create a simple query that selects specific columns and applies filters:

```py

df = (
    tables['default'] # Select the 'default' table as our data source
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

!!!note
    The `to_pandas_dataframe` method executes the query and returns the results as a Pandas DataFrame.

!!! tip "Chained Methods"
    The query methods can be chained together to build complex queries in a readable manner.

For more detailed information on the available methods and options for querying, refer to the [Client Reference](reference/client.md), [Table Reference](reference/table.md), and [Query Reference](reference/query.md) sections of the documentation.

!!!info "Alternative Query Creation"
    The query can also be created using the client directly, by default it will use the `default` table:
    ```py
    df = (
        client.query()
        .add_select_column("LONGITUDE")
        .add_select_column("LATITUDE")
        .add_select_column("JULD")
        .add_select_column("PRES")
        .add_select_column("TEMP")
        .add_select_column("PSAL")
        .add_select_column(".featureType")
        .add_select_column("DATA_TYPE")
        .add_range_filter("JULD", "2020-01-01T00:00:00", "2021-01-01T00:00:00")
        .add_range_filter("PRES", 0, 10)
        .to_pandas_dataframe()
    )
    df
    ```
