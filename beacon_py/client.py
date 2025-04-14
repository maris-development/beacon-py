from __future__ import annotations
from sqlalchemy import *
from sqlalchemy.orm import DeclarativeMeta
import requests
import table
import pandas as pd

class Client:
    def __init__(self, url: str, headers: dict=None):
        # Set JSON headers
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'
        
        self.url = url
        self.session = requests.Session()
        self.session.headers.update(headers or {})
        self.model_factory = table.ModelFactory()
        
        # Init the client by:
        #   Getting all the data tables
        #   Getting all the available columns
    
    def list_tables(self) -> list[str]:
        """Get all the tables"""
        pass
    
    def list_datasets(self) -> list[str]:
        pass
    
    def table(self, table_name: str):
        """Get a QueryableDataTable object"""
        pass
    
    def dataset(self, dataset_name: str):
        """Get a QueryableDataTable object"""
        pass
    
    def query_to_pandas(self, statement: Select) -> pd.DataFrame:
        pass
    
    
