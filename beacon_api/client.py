"""High-level Beacon API client used to interact with Beacon Nodes.

The :class:`Client` wraps the low-level :class:`~beacon_api.session.BaseBeaconSession`
to expose discoverability helpers (listing tables/datasets), querying shortcuts,
and backwards-compatible deprecated entry points. Docstrings follow the public
SDK documentation style so IDEs surface helpful call hints.
"""

from __future__ import annotations
import datetime
import requests
from typing import Optional
from deprecated import deprecated

from .session import BaseBeaconSession
from .table import DataTable
from .dataset import Dataset
from .query import JSONQuery, SQLQuery, FromTable

class Client:
    """
    A ``Client`` provides a connection to a Beacon Node, manages authentication headers and exposes helpers for
    discovering tables/datasets before building JSON or SQL queries.
    """

    def __init__(self, url: str, proxy_headers: dict[str,str] | None = None, jwt_token: str | None = None, basic_auth: tuple[str, str] | None = None):
        """Create a Beacon API client.

        Args:
            url: Base Beacon Node URL, e.g. ``"https://beacon-node.example.com"``.
            proxy_headers: Optional custom headers added to every request.
            jwt_token: Optional bearer token used for ``Authorization`` header.
            basic_auth: Optional ``(username, password)`` tuple for HTTP basic auth.

        Raises:
            ValueError: If ``basic_auth`` is not a 2-item tuple.
            Exception: When the Beacon Node health endpoint cannot be reached.
        """
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
            proxy_headers['Authorization'] = f'{requests.auth._basic_auth_str(*basic_auth)}' # type: ignore
        
        self.session = BaseBeaconSession(url)
        self.session.headers.update(proxy_headers)
        
        if self.check_status():
            raise Exception("Failed to connect to server")
        
    def check_status(self):
        """Verify that the Beacon Node responds to ``/api/health``.

        Returns:
            None. The method prints diagnostic information on success.

        Raises:
            Exception: If the Beacon Node returns a non-200 response.
        """
        response = self.session.get("api/health")
        if response.status_code != 200:
            raise Exception(f"Failed to connect to server: {response.text}")
        else:
            print("Connected to: {} server successfully".format(self.session.base_url))
            print("Beacon Version:", self.get_server_info()['beacon_version'])
            
    def get_server_info(self) -> dict:
        """Return the server metadata exposed by ``/api/info``."""
        response = self.session.get("/api/info")
        if response.status_code != 200:
            raise Exception(f"Failed to get server info: {response.text}")
        return response.json()

    @deprecated(version="1.1.0",reason="Use list_tables() to get available tables. From there you can find the available columns for each table. This method will be removed in future versions.")
    def available_columns(self) -> list[str]:
        """Return column names for the default table (deprecated)."""
        response = self.session.get("/api/query/available-columns")
        if response.status_code != 200:
            raise Exception(f"Failed to get columns: {response.text}")
        columns = response.json()
        return columns
    
    @deprecated(version="1.1.0",reason="Use list_tables() to get available tables. From there you can find the available columns and their data types for each table. This method will be removed in future versions.")
    def available_columns_with_data_type(self) -> dict[str, type]:
        tables = self.list_tables()
        if 'default' not in tables:
            raise Exception("No default table found")
        table = tables['default']
        return table.get_table_schema()
    
    def list_tables(self) -> dict[str,DataTable]:
        """Retrieve all logical tables available on the Beacon Node.

        Returns:
            dict[str, DataTable]: Mapping of table name to :class:`DataTable` helper.
        """
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
    
    def list_datasets(self, pattern: str | None = None, limit : int | None = None, offset: int | None = None, force=False) -> dict[str, Dataset]:
        """Enumerate datasets registered with the Beacon node.

        Args:
            pattern: Optional glob-like filter applied by the server.
            limit: Optional page size to cap the number of results.
            offset: Optional offset for pagination.

        Returns:
            dict[str, Dataset]: Mapping from file path to :class:`Dataset` helper.

        Raises:
            Exception: If the Beacon Node version < 1.4.0 or the HTTP call fails.
        """
        
        if not force and not self.session.version_at_least(1,4,0):
            raise Exception("Listing datasets requires Beacon server version 1.4.0 or higher")
        
        response = self.session.get("/api/list-datasets", params={
            "pattern": pattern,
            "limit": limit,
            "offset": offset
        })
        if response.status_code != 200:
            raise Exception(f"Failed to get datasets: {response.text}")
        datasets = response.json()
        dataset_objects = {}
        for dataset in datasets:
            file_path = dataset['file_path']
            file_format = dataset['format']
            
            dataset_objects[file_path] = Dataset(
                http_session=self.session,
                file_path=file_path,
                file_format=file_format
            )
        return dataset_objects
    
    def sql_query(self, sql: str) -> SQLQuery:
        """Create a new :class:`SQLQuery` for direct SQL execution.

        Args:
            sql: Raw SQL string sent to the Beacon Node.

        Returns:
            SQLQuery: Builder that exposes ``to_dataframe``, ``to_csv`` etc.
        """
        return SQLQuery(http_session=self.session, query=sql)

    @deprecated("To query, use list_tables() or list_datasets() as a base to create a new query object. This method will be removed in future versions.")
    def query(self) -> JSONQuery:
        """Create a new query object. 
        This is the starting point for building a query.
        The query can then be built using the methods on the Query object.
        You can also create a query from a specific table from the list_tables() method.
        
        To materialize and run the query, use the .to_dataframe() or .to_csv() methods on the Query object.
        Returns:
            JSONQuery: A new query object.
        """
        
        # Get the default table and use it as the from source
        response = self.session.get("/api/default-table")  # Ensure default table exists
        if response.status_code != 200:
            raise Exception(f"Failed to get default table: {response.text}")
        default_table = response.json()
        return JSONQuery(http_session=self.session, _from=FromTable(default_table))
    
    @deprecated("Use the subset method on the DataTable object obtained from list_tables(). This method will be removed in future versions.")
    def subset(self, longitude_column: str, latitude_column: str, time_column: str, depth_column: str, columns: list[str],
                         bbox: Optional[tuple[float, float, float, float]] = None,
                         depth_range: Optional[tuple[float, float]] = None,
                         time_range: Optional[tuple[datetime.datetime, datetime.datetime]] = None) -> JSONQuery:
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
            JSONQuery: Query object that can be executed to retrieve the subset.
        """
        response = self.session.get("/api/default-table")  # Ensure default table exists
        if response.status_code != 200:
            raise Exception(f"Failed to get default table: {response.text}")
        default_table = response.json()
        
        table = self.list_tables()[default_table]
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
        
    def upload_dataset(self, file_path: str, destination_path: str, force=False) -> None:
        """Upload a local dataset file to the Beacon Node.

        Args:
            file_path: Path to the local file to upload.
            destination_path: Destination path on the Beacon Node.

        Raises:
            Exception: If the upload fails.
        """
        
        # Require Beacon server version >= 1.5.0
        if not force and not self.session.version_at_least(1,5,0):
            raise Exception("Uploading datasets requires Beacon server version 1.5.0 or higher")
        
        # Requires admin privileges
        if not self.session.is_admin():
            raise Exception("Uploading datasets requires admin privileges")
        
        # We use requests directly here to support multipart/form-data 
        auth_headers = {
            "Authorization": self.session.headers.get("Authorization", "")
        }
        url = f"{self.session.base_url}/api/admin/upload-file"
        
        # Upload the file using a multipart/form-data POST request
        # the first part should be the prefix of the destination path eg. /data/datasets/ of /data/datasets/myfile.parquet
        prefix = '/'.join(destination_path.split('/')[:-1])
        # File name is the last part
        file_name = destination_path.split('/')[-1]
        payload = {'prefix': prefix }
        files=[
            ('file',(file_name,open(file_path,'rb'),'application/octet-stream'))
        ]
        response = requests.request("POST", url, headers=auth_headers, data=payload, files=files)
        if response.status_code != 200:
            raise Exception(f"Failed to upload dataset: {response.text}")        
            

    def download_dataset(self, dataset_path: str, local_path: str, force=False) -> None:
        """Download a dataset file from the Beacon Node to a local path.

        Args:
            dataset_path: Path to the dataset file on the Beacon Node.
            local_path: Local path where the file will be saved.
        Raises:
            Exception: If the download fails.
        """
        # Require Beacon server version >= 1.5.0
        if not force and not self.session.version_at_least(1,5,0):
            raise Exception("Downloading datasets requires Beacon server version 1.5.0 or higher")
        
        # Requires admin privileges
        if not self.session.is_admin():
            raise Exception("Downloading datasets requires admin privileges")
        
        response = self.session.get("/api/admin/download-file", params={
            "file_path": dataset_path
        }, stream=True)
        if response.status_code != 200:
            raise Exception(f"Failed to download dataset: {response.text}")
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def delete_dataset(self, dataset_path: str, force=False) -> None:
        """Delete a dataset file from the Beacon Node.

        Args:
            dataset_path: Path to the dataset file on the Beacon Node.
            
        Raises:
            Exception: If the deletion fails.
        """
        
        # Require Beacon server version >= 1.5.0
        if not force and not self.session.version_at_least(1,5,0):
            raise Exception("Deleting datasets requires Beacon server version 1.5.0 or higher")
        
        # Requires admin privileges
        if not self.session.is_admin():
            raise Exception("Deleting datasets requires admin privileges")
        
        response = self.session.delete("/api/admin/delete-file", params={
            "file_path": dataset_path
        })
        if response.status_code != 200:
            raise Exception(f"Failed to delete dataset: {response.text}")
        
    def create_logical_table(self, table_name: str, dataset_glob_paths: list[str], file_format: str, description: str | None = None, force=False, **kwargs) -> None:
        """Create a new logical table on the Beacon Node.

        Args:
            table_name: Name of the new logical table.
            dataset_glob_paths: List of dataset file paths (can include glob patterns).
            file_format: Format of the dataset files (e.g. "parquet", "csv", "zarr").
            description: Optional description of the logical table.
            **kwargs: Additional parameters specific to the file format. (e.g. delimiter for CSV, Zarr statistics columns)

        Raises:
            Exception: If the creation fails.
        """
        
        # Require Beacon server version >= 1.4.0
        if not force and not self.session.version_at_least(1,4,0):
            raise Exception("Creating logical tables requires Beacon server version 1.4.0 or higher")
        
        # Requires admin privileges
        if not self.session.is_admin():
            raise Exception("Creating logical tables requires admin privileges")
        
        json_data = {
            "table_name": table_name,
            "table_type": {
                "logical": {
                    "glob_paths": dataset_glob_paths,
                    "file_format": file_format,
                    **kwargs
                }
            },
            "description": description
        }
        
        response = self.session.post("/api/admin/create-table", json=json_data)
        if response.status_code != 200:
            raise Exception(f"Failed to create table: {response.text}")
        
    def delete_table(self, table_name: str, force=False) -> None:
        """Delete a logical table from the Beacon Node.

        Args:
            table_name: Name of the logical table to delete.
        Raises:
            Exception: If the deletion fails.
        """
        
        # Require Beacon server version >= 1.4.0
        if not force and not self.session.version_at_least(1,4,0):
            raise Exception("Deleting logical tables requires Beacon server version 1.4.0 or higher")
        
        # Requires admin privileges
        if not self.session.is_admin():
            raise Exception("Deleting logical tables requires admin privileges")
        
        response = self.session.delete("/api/admin/delete-table", params={
            "table_name": table_name
        })
        if response.status_code != 200:
            raise Exception(f"Failed to delete table: {response.text}")