# Data Tables / Data Collections

In the Beacon Data Lake, data is organized into tables (also referred to as data collections). Each table contains a set of columns originating from the datasets stored inside the data lake. You can interact with these tables using the `beacon_api` package to perform queries and retrieve data.
Each table is represented by a `Table` object in the `beacon_api` package. You can obtain a `Table` object by listing the available tables in the connected Beacon Data Lake using the `list_tables` method of the `Client` object.

```py
tables = client.list_tables()
print(tables)  # This will print a dictionary of available tables
```

You can access a specific table by its name from the dictionary returned by `list_tables`. For example, to access a table named `vessels`, you can do the following:

```py
vessels_table = tables['vessels']
print(vessels_table)  # This will print the Table object for the 'vessels' table
```

Once you have a `Table` object, you can view its schema (available columns) using the `get_table_schema` method:

```py
schema = vessels_table.get_table_schema()
print(schema)  # This will print the schema of the 'vessels' table
```

You can also create and execute queries on the table using the `query` method of the `Table` object. This will return a `Query` object that you can use to build and execute your query.

```py
query = vessels_table.query()
# You can then build your query using the Query methods
```
