from client import Client
import table

client = Client("http://localhost:5001")

# print(client.available_columns())
# print(client.list_tables())
# print(client.list_datasets())
emodnet = client.table("emodnet_chemistry")


