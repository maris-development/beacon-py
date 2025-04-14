from __future__ import annotations
from sqlalchemy import *
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy.dialects import postgresql
import requests
from requests import Session
from table import build_data_table
from io import BytesIO
import pandas as pd

class Client:
    def __init__(self, url: str, proxy_headers: dict=None):
        if proxy_headers is None:
            proxy_headers = {}
        # Set JSON headers
        proxy_headers['Content-Type'] = 'application/json'
        proxy_headers['Accept'] = 'application/json'
        
        self.url = url
        self.session = requests.Session()
        self.session.headers.update(proxy_headers)
        
        # Get all table definitions
        
        if self.check_status():
            raise Exception("Failed to connect to server")
        
    def check_status(self):
        """Check the status of the server"""
        response = self.session.get(f"{self.url}/api/health")
        if response.status_code != 200:
            raise Exception(f"Failed to connect to server: {response.text}")
        
    def available_columns(self) -> list[str]:
        """Get all the available columns for the default data table"""
        endpoint = f"{self.url}/api/query/available-columns"
        response = self.session.get(endpoint)
        if response.status_code != 200:
            raise Exception(f"Failed to get columns: {response.text}")
        columns = response.json()
        return columns
    
    def list_tables(self) -> list[str]:
        """Get all the tables"""
        endpoint = f"{self.url}/api/tables"
        response = self.session.get(endpoint)
        if response.status_code != 200:
            raise Exception(f"Failed to get tables: {response.text}")
        tables = response.json()
        return tables
    
    def list_datasets(self, pattern: str | None = None, limit : int | None = None, offset: int | None = None) -> list[str]:
        """Get all the datasets"""
        endpoint = f"{self.url}/api/datasets"
        response = self.session.get(endpoint, params={
            "pattern": pattern,
            "limit": limit,
            "offset": offset
        })
        if response.status_code != 200:
            raise Exception(f"Failed to get datasets: {response.text}")
        datasets = response.json()
        return datasets
    
    def default_table(self) -> table.QueryableDataTable:
        """Get the default table"""
        endpoint = f"{self.url}/api/default-table"
        pass
    
    def table(self, table_name: str) -> type:
        """Get a QueryableDataTable object"""
        endpoint = f"{self.url}/api/table-schema"
        response = self.session.get(endpoint, params={"table_name": table_name})
        table = build_data_table(table_name,response.json())
        return table
    
    def dataset(self, dataset_name: str) -> table.QueryableDataTable:
        """Get a QueryableDataTable object"""
        endpoint = f"{self.url}/api/dataset-schema"
        response = self.session.get(endpoint, params={"file": dataset_name})
        table = table.build_data_table(response.json())
        return table
    
    def query_to_pandas(self, statement: Select) -> pd.DataFrame:
        """Query to a pandas DataFrame"""
        # Convert the SQLAlchemy statement to a string
        compiled_query = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        print(compiled_query)
        # Send the query to the server
        endpoint = f"{self.url}/api/query"
        response = self.session.post(endpoint, json={
            "sql": compiled_query,
            "output": {
                "format": "parquet"
            }
        })
        
        if response.status_code != 200:
            raise Exception(f"Failed to execute query: {response.text}")
        
        # Convert the response to a pandas DataFrame
        print(len(response.content))
        bytes = response.content
        df = pd.read_parquet(BytesIO(bytes))
        
        return df