from __future__ import annotations
import requests
from requests import Session
from io import BytesIO
import pandas as pd
from beacon_api.session import BaseBeaconSession
from beacon_api.table import DataTable

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
    
    def list_datasets(self, pattern: str | None = None, limit : int | None = None, offset: int | None = None) -> list[str]:
        """Get all the datasets"""
        response = self.session.get("/api/datasets", params={
            "pattern": pattern,
            "limit": limit,
            "offset": offset
        })
        if response.status_code != 200:
            raise Exception(f"Failed to get datasets: {response.text}")
        datasets = response.json()
        return datasets
    
    def query(self): 
        pass