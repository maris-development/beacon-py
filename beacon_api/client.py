from __future__ import annotations
import datetime
from typing import Optional
import requests
import pandas as pd
from requests import Session
from io import BytesIO

from .query import Query
from .session import BaseBeaconSession
from .table import DataTable
from .dataset import Dataset

class Client:
    def __init__(self, url: str, proxy_headers: dict[str,str] | None = None, jwt_token: str | None = None, basic_auth: tuple[str, str] | None = None):
        if proxy_headers is None:
            proxy_headers = {}
        # Set JSON headers
        proxy_headers['Content-Type'] = 'application/json'
        proxy_headers['Accept'] = 'application/json'
        if jwt_token:
            proxy_headers['Authorization'] = f'Bearer {jwt_token}'
            
        if basic_auth:
            if not isinstance(basic_auth, tuple) or len(basic_auth) != 2:
                raise ValueError("Basic auth must be a tuple of (username, password)")
            proxy_headers['Authorization'] = f'Basic {requests.auth._basic_auth_str(*basic_auth)}' # type: ignore
        
        self.session = BaseBeaconSession(url)
        self.session.headers.update(proxy_headers)
        
        if self.check_status():
            raise Exception("Failed to connect to server")
        
    def check_status(self):
        """Check the status of the server"""
        response = self.session.get("api/health")
        if response.status_code != 200:
            raise Exception(f"Failed to connect to server: {response.text}")
        else:
            print("Connected to: {} server successfully".format(self.session.base_url))

    def available_columns(self) -> list[str]:
        """Get all the available columns for the default data table"""
        response = self.session.get("/api/query/available-columns")
        if response.status_code != 200:
            raise Exception(f"Failed to get columns: {response.text}")
        columns = response.json()
        return columns
    
    def available_columns_with_data_type(self) -> dict[str, type]:
        tables = self.list_tables()
        if 'default' not in tables:
            raise Exception("No default table found")
        table = tables['default']
        return table.get_table_schema()
    
    def list_tables(self) -> dict[str,DataTable]:
        """Get all the tables"""
        response = self.session.get("/api/tables")
        if response.status_code != 200:
            raise Exception(f"Failed to get tables: {response.text}")
        tables = response.json()
        
        data_tables = {}
        for table in tables:
            data_tables[table] = DataTable(
                http_session=self.session,
                table_name=table,
            )
        
        return data_tables
    
    def list_datasets(self, pattern: str | None = None, limit : int | None = None, offset: int | None = None) -> dict[str, Dataset]:
        """Get all the datasets"""
        response = self.session.get("/api/datasets", params={
            "pattern": pattern,
            "limit": limit,
            "offset": offset
        })
        if response.status_code != 200:
            raise Exception(f"Failed to get datasets: {response.text}")
        datasets = response.json()
        dataset_objects = {}
        for dataset in datasets:
            dataset_objects[dataset] = Dataset(
                http_session=self.session,
                file_path=dataset
            )
        return dataset_objects

    def query(self) -> Query:
        """Create a new query object. 
        This is the starting point for building a query.
        The query can then be built using the methods on the Query object.
        You can also create a query from a specific table from the list_tables() method.
        
        To materialize and run the query, use the .to_dataframe() or .to_csv() methods on the Query object.
        Returns:
            Query: A new query object.
        """
        return Query(http_session=self.session, from_table="default")
    
    def subset(self, longitude_column: str, latitude_column: str, time_column: str, depth_column: str, columns: list[str],
                         bbox: Optional[tuple[float, float, float, float]] = None,
                         depth_range: Optional[tuple[float, float]] = None,
                         time_range: Optional[tuple[datetime.datetime, datetime.datetime]] = None) -> Query:
        """
        Create a query to subset the default collection based on the provided parameters.
        
        Args:
            longitude_column: Name of the column containing longitude values.
            latitude_column: Name of the column containing latitude values.
            time_column: Name of the column containing time values.
            depth_column: Name of the column containing depth values.
            columns: List of additional columns to include in the query.
            bbox: Optional bounding box defined as (min_longitude, min_latitude, max_longitude, max_latitude).
            depth_range: Optional range for depth defined as (min_depth, max_depth).
            time_range: Optional range for time defined as (start_time, end_time).
        Returns
            A Query object that can be executed to retrieve the subset of data.
        """
        table = self.list_tables()['default']
        return table.subset(
            longitude_column=longitude_column,
            latitude_column=latitude_column,
            time_column=time_column,
            depth_column=depth_column,
            columns=columns,
            bbox=bbox,
            depth_range=depth_range,
            time_range=time_range
        )
