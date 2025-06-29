from datetime import datetime
import json
from beacon_api import *
from beacon_api.query import IsNotNullFilter, RangeFilter, Parquet

client = Client("http://localhost:5001")
tables = client.list_tables()
# print(tables)

table = tables['bgc']

# print(table.get_table_schema())

df = table.peek(
    longitude_column="LONGITUDE",
    latitude_column="LATITUDE",
    time_column="TIME",
    depth_column="DEPH",
    columns=["CHLT", "CHLT.standard_name", "CHLT.units"],
    bbox=(-180.0, -90.0, 180.0, 90.0),
    time_range=(datetime(2020, 1, 1), datetime(2020, 12, 31, 23, 59, 59))
).set_output(Parquet()).explain_visualize()

print(df)

# query = table.query()
# query.add_select_column("TIME")
# query.add_select_column("CHLT.standard_name")
# query.add_filter(RangeFilter("TIME", "2020-01-01T00:00:00", "2020-12-31T23:59:59"))
# query.add_filter(IsNotNullFilter("CHLT.standard_name"))
# query.set_output(Parquet())
# # df = query.to_pandas_dataframe()
# print(query.to_pandas_dataframe())