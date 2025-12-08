import atexit
import json
import os
import tempfile
from typing import Generator, Iterator
import pandas as pd
import geopandas as gpd
import xarray as xr
import dask.dataframe as dd
import fsspec
from io import BytesIO
from abc import abstractmethod
from requests import Response
from pyarrow import parquet as pq
import pyarrow as pa
import pyarrow.ipc as ipc

from datetime import datetime

try:
    from typing import Optional
    from typing import List
    from typing import Self
    from typing import Union
    from typing import Tuple
except ImportError:
    from typing_extensions import Optional
    from typing_extensions import List
    from typing_extensions import Self
    from typing_extensions import Tuple
    from typing_extensions import Union

from .node import *
from ._from import *
from .functions import *
from .output import *
from .select import *
from .filter import *
from .distinct import *
from .sort import *
from ..session import BaseBeaconSession

class BaseQuery:
    def __init__(self, http_session: BaseBeaconSession):
        self.http_session = http_session
        self.output_format = None
        
    @abstractmethod
    def compile(self) -> dict:
        ...
    
    def set_output(self, output_format: Output) -> None:
        """Set the output format for the query"""
        self.output_format = output_format
    
    def output(self) -> dict:
        """Get the output format of the query, if specified"""
        return {
            "output": self.output_format.to_dict() if self.output_format else None
        }
        
    def compile_query(self) -> str:
        """Compile the query to a JSON string"""
        query_body_dict = self.output() | self.compile()
        
        def datetime_converter(o):
            if isinstance(o, datetime):
                return o.strftime("%Y-%m-%dT%H:%M:%S.%f")
            raise TypeError(f"Type {type(o)} not serializable")

        query_body = json.dumps(query_body_dict, default=datetime_converter)
        return query_body

    def explain(self) -> dict:
        """Get the query plan"""
        query = self.compile_query()
        response = self.http_session.post("/api/explain-query", data=query)
        if response.status_code != 200:
            raise Exception(f"Explain query failed: {response.text}")
        return response.json()

    def execute(self, stream=False) -> Response:
        """Run the query and return the response"""
        query_body = self.compile_query()
        print(f"Running query: {query_body}")
        response = self.http_session.post("/api/query", data=query_body, stream=stream)
        if response.status_code != 200:
            raise Exception(f"Query failed: {response.text}")
        if len(response.content) == 0:
            raise Exception("Query returned no content")
        return response
    
    def execute_streaming(self, force=False) -> Iterator[pa.RecordBatch]:
        """Run the query and return the response as a streaming response"""
        if not force and not self.http_session.version_at_least(1, 5, 0):
            raise Exception("Streaming queries require the Beacon Node version to be atleast 1.5.0 or higher")
        
        query_body = self.compile_query()
        print(f"Running query: {query_body}")
        response = self.http_session.post("/api/query", data=query_body, stream=True)

        stream = ipc.open_stream(response.raw)

        for batch in stream:
            yield batch
    
    def to_xarray_dataset(self, dimension_columns: List[str], chunks: Union[dict, None] = None, auto_cleanup=True, force=False) -> xr.Dataset:
        """Converts the query results to an xarray Dataset with n-dimensional structure.

        Args:
            dimension_columns (list[str]): The list of columns to use as dimensions in the xarray Dataset.

        Returns:
            xarray.Dataset: The query results as an xarray Dataset.
        """
        if not force and not self.http_session.version_at_least(1, 5, 0):
            raise Exception("xarray dataset output requires the Beacon Node version to be atleast 1.5.0 or higher")
        
        # create tempfile for the netcdf file
        fd, path = tempfile.mkstemp(suffix=".nc")
        self.to_nd_netcdf(file_path=path, dimension_columns=dimension_columns,force=force)

        ds = xr.open_dataset(path, chunks=chunks)
        # register for cleanup the tempfile
        if auto_cleanup:
            atexit.register(lambda: os.path.exists(path) and os.remove(path))
        
        return ds

    def to_pandas_dataframe(self) -> pd.DataFrame:
        """Execute the query and return the results as a pandas DataFrame"""
        self.set_output(Parquet())
        response = self.execute()
        bytes_io = BytesIO(response.content)
        return pd.read_parquet(bytes_io)
    
    def to_geo_pandas_dataframe(self, longitude_column: str, latitude_column: str, crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
        """Converts the query results to a GeoPandas GeoDataFrame.

        Args:
            longitude_column (str): The name of the column representing longitude.
            latitude_column (str): The name of the column representing latitude.
            crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:4326".

        Returns:
            gpd.GeoDataFrame: The query results as a GeoPandas GeoDataFrame.
        """
        
        self.set_output(GeoParquet(longitude_column=longitude_column, latitude_column=latitude_column))
        response = self.execute()
        bytes_io = BytesIO(response.content)
        # Read into parquet arrow table 
        table = pq.read_table(bytes_io)
        
        gdf = gpd.GeoDataFrame.from_arrow(table)
        gdf.set_crs(crs, inplace=True)
        return gdf
    
    def to_parquet(self, file_path: str, streaming_chunk_size: int = 1024*1024):
        """Execute the query and save the results as a Parquet file"""
        self.set_output(Parquet())
        response = self.execute()
        with open(file_path, "wb") as f:
            # Write the content of the response to a file
            for chunk in response.iter_content(chunk_size=streaming_chunk_size):
                if chunk:  # skip keep-alive chunks
                    f.write(chunk)
                    
    def to_geoparquet(self, file_path: str, longitude_column: str, latitude_column: str, streaming_chunk_size: int = 1024*1024):
        """Execute the query and save the results as a GeoParquet file"""
        self.set_output(GeoParquet(longitude_column=longitude_column, latitude_column=latitude_column))
        response = self.execute()
        with open(file_path, "wb") as f:
            # Write the content of the response to a file
            for chunk in response.iter_content(chunk_size=streaming_chunk_size):
                if chunk:  # skip keep-alive chunks
                    f.write(chunk)
                    
    def to_csv(self, file_path: str, streaming_chunk_size: int = 1024*1024):
        """Execute the query and save the results as a CSV file"""
        self.set_output(CSV())
        response = self.execute()
        with open(file_path, "wb") as f:
            # Write the content of the response to a file
            for chunk in response.iter_content(chunk_size=streaming_chunk_size):
                if chunk:  # skip keep-alive chunks
                    f.write(chunk)
                    
    def to_arrow(self, file_path: str, streaming_chunk_size: int = 1024*1024):
        """Execute the query and save the results as an Arrow file"""
        self.set_output(Arrow())
        response = self.execute()
        with open(file_path, "wb") as f:
            # Write the content of the response to a file
            for chunk in response.iter_content(chunk_size=streaming_chunk_size):
                if chunk:  # skip keep-alive chunks
                    f.write(chunk)
    
    def to_netcdf(self, file_path: str, build_nc_local:bool = True, streaming_chunk_size: int = 1024*1024):
        """Execute the query and save the results as an NetCDF file"""
        if build_nc_local:
            df = self.to_pandas_dataframe()
            xdf = df.to_xarray()
            xdf.to_netcdf(file_path, mode="w")
        else:
            self.set_output(NetCDF())  # Specify dimension columns as needed
            response = self.execute()
            with open(file_path, "wb") as f:
                # Write the content of the response to a file
                for chunk in response.iter_content(chunk_size=streaming_chunk_size):
                    if chunk:  # skip keep-alive chunks
                        f.write(chunk)
                        
    def to_nd_netcdf(self, file_path: str, dimension_columns: list[str], streaming_chunk_size: int = 1024*1024, force: bool = False):
        """Execute the query and save the results as an NdNetCDF file"""
        if not force and not self.http_session.version_at_least(1, 5, 0):
            raise Exception("NdNetCDF output format requires the Beacon Node version to be atleast 1.5.0 or higher")
        self.set_output(NdNetCDF(dimension_columns=dimension_columns))
        response = self.execute()
        with open(file_path, "wb") as f:
            # Write the content of the response to a file
            for chunk in response.iter_content(chunk_size=streaming_chunk_size):
                if chunk:  # skip keep-alive chunks
                    f.write(chunk)
        
    def to_zarr(self, file_path: str):
        # Read to pandas dataframe first
        df = self.to_pandas_dataframe()
        # Convert to Zarr format
        xdf = df.to_xarray()
        xdf.to_zarr(file_path, mode="w")
        
    def to_odv(self, odv_output: Odv, file_path: str):
        """Exports the query results to an ODV file.

        Args:
            odv_output (Odv): The ODV output format to use.
            file_path (str): The path to the file where the ODV data will be saved.
        """
        self.set_output(odv_output)
        response = self.execute()
        with open(file_path, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)
        
class SQLQuery(BaseQuery):
    def __init__(self, http_session: BaseBeaconSession, query: str):
        super().__init__(http_session)
        self.query = query
        
    def compile(self) -> dict:
        return {"sql": self.query}

class JSONQuery(BaseQuery):
    def __init__(self, http_session: BaseBeaconSession, _from: From):
        print(f"Creating JSONQuery with from: {_from}")
        super().__init__(http_session)
        self._from = _from
        self.selects = []
        self.filters = []
        self.sorts = []
        self.distinct = None
    
    def compile(self) -> dict:
        return {
            "select": [s.to_dict() for s in self.selects],
            "filters": [f.to_dict() for f in self.filters] if self.filters else None,
            "distinct": self.distinct.to_dict() if self.distinct else None,
            **self._from.to_dict(),
        }
    
    def select(self, selects: List[Select]) -> Self:
        self.selects = selects
        return self

    def add_select(self, select: Select) -> Self:
        self.selects.append(select)
        return self

    def add_selects(self, selects: List[Select]) -> Self:
        """Adds multiple select statements to the query.

        Args:
            selects (list[Select]): The select statements to add.

        Returns:
            Self: The query builder instance.
        """
        self.selects.extend(selects)
        return self

    def add_select_column(self, column: str, alias: Optional[str] = None) -> Self:
        """Adds a select column to the query.

        Args:
            column (str): The name of the column to select.
            alias (str | None, optional): An optional alias for the column. Defaults to None.

        Returns:
            Self: The query builder instance.
        """
        self.selects.append(SelectColumn(column=column, alias=alias))
        return self

    def add_select_columns(self, columns: List[Tuple[str, Optional[str]]]) -> Self:
        """Adds multiple select columns to the query.

        Args:
            columns (List[Tuple[str, Optional[str]]]): A list of tuples containing column names and their aliases.

        Returns:
            Self: The query builder instance.
        """
        for column, alias in columns:
            self.selects.append(SelectColumn(column=column, alias=alias))
        return self

    def add_select_coalesced(self, mergeable_columns: List[str], alias: str) -> Self:
        """Adds a coalesced select to the query.

        Args:
            mergeable_columns (list[str]): The columns to merge.
            alias (str): The alias for the merged column.

        Returns:
            Self: The query builder instance.
        """
        function_call = SelectFunction("coalesce", args=[SelectColumn(column=col) for col in mergeable_columns], alias=alias)
        self.selects.append(function_call)
        return self

    def filter(self, filters: List[Filter]) -> Self:
        """Adds filters to the query.

        Args:
            filters (list[Filter]): The filters to add.

        Returns:
            Self: The query builder instance.
        """
        self.filters = filters
        return self

    def add_filter(self, filter: Filter) -> Self:
        """Adds a filter to the query.

        Args:
            filter (Filter): The filter to add.

        Returns:
            Self: The query builder instance.
        """
        self.filters.append(filter)
        return self

    def add_bbox_filter(
        self,
        longitude_column: str,
        latitude_column: str,
        bbox: Tuple[float, float, float, float],
    ) -> Self:
        """Adds a bounding box filter to the query.

        Args:
            longitude_column (str): The name of the column for longitude.
            latitude_column (str): The name of the column for latitude.
            bbox (tuple[float, float, float, float]): The bounding box coordinates (min_lon, min_lat, max_lon, max_lat).

        Returns:
            Self: The query builder instance.
        """
        self.filters.append(
            AndFilter(
                filters=[
                    RangeFilter(column=longitude_column, gt_eq=bbox[0]),
                    RangeFilter(column=longitude_column, lt_eq=bbox[2]),
                    RangeFilter(column=latitude_column, gt_eq=bbox[1]),
                    RangeFilter(column=latitude_column, lt_eq=bbox[3]),
                ]
            )
        )
        return self

    def add_polygon_filter(self, longitude_column: str, latitude_column: str, polygon: List[Tuple[float, float]]) -> Self:
        """Adds a POLYGON filter to the query.

        Args:
            longitude_column (str): The name of the column for longitude.
            latitude_column (str): The name of the column for latitude.
            polygon (list[tuple[float, float]]): A list of (longitude, latitude) tuples defining the polygon.

        Returns:
            Self: The query builder instance.
        """
        self.filters.append(PolygonFilter(longitude_column=longitude_column, latitude_column=latitude_column, polygon=polygon))
        return self

    def add_range_filter(
        self,
        column: str,
        gt_eq: Union[str, int, float, datetime, None] = None,
        lt_eq: Union[str, int, float, datetime, None] = None,
        gt: Union[str, int, float, datetime, None] = None,
        lt: Union[str, int, float, datetime, None] = None
    ) -> Self:
        """Adds a RANGE filter to the query.

        Args:
            column (str): The name of the column to filter.
            gt_eq (str | int | float | datetime | None, optional): The lower bound for the range filter. Defaults to None.
            lt_eq (str | int | float | datetime | None, optional): The upper bound for the range filter. Defaults to None.
            gt (str | int | float | datetime | None, optional): The exclusive lower bound for the range filter. Defaults to None.
            lt (str | int | float | datetime | None, optional): The exclusive upper bound for the range filter. Defaults to None.
        Returns:
            Self: The query builder instance.
        """
        if gt_eq is not None or lt_eq is not None:
            self.filters.append(RangeFilter(column=column, gt_eq=gt_eq, lt_eq=lt_eq))

        if gt is not None or lt is not None:
            self.filters.append(ExclusiveRangeFilter(column=column, gt=gt, lt=lt))
        
        return self

    def add_equals_filter(
        self, column: str, eq: Union[str, int, float, bool, datetime]
    ) -> Self:
        """Adds an EQUALS filter to the query.

        Args:
            column (str): The name of the column to filter.
            eq (str | int | float | bool | datetime): The value to compare against.

        Returns:
            Self: The query builder instance.
        """
        self.filters.append(EqualsFilter(column=column, eq=eq))
        return self

    def add_not_equals_filter(
        self, column: str, neq: Union[str, int, float, bool, datetime]
    ) -> Self:
        """Adds a NOT EQUALS filter to the query.

        Args:
            column (str): The name of the column to filter.
            neq (str | int | float | bool | datetime): The value to compare against.

        Returns:
            Self: The query builder instance.
        """

        self.filters.append(NotEqualsFilter(column=column, neq=neq))
        return self

    def add_is_null_filter(self, column: str) -> Self:
        """Adds an IS NULL filter to the query.

        Args:
            column (str): The name of the column to filter.

        Returns:
            Self: The query builder instance.
        """
        self.filters.append(FilterIsNull(column=column))
        return self

    def add_is_not_null_filter(self, column: str) -> Self:
        """Adds an IS NOT NULL filter to the query.

        Args:
            column (str): The name of the column to filter.

        Returns:
            Self: The query builder instance.
        """
        self.filters.append(IsNotNullFilter(column=column))
        return self
    
    def set_distinct(self, columns: list[str]) -> Self:
        """Adds a DISTINCT clause to the query.

        Args:
            columns (list[str]): The list of columns to apply DISTINCT on.

        Returns:
            Self: The query builder instance.
        """
        self.distinct = Distinct(columns=columns)
        return self
    
    def add_sort(self, column: str, ascending: bool = True) -> Self:
        """Adds a SORT clause to the query.

        Args:
            column (str): The name of the column to sort by.
            ascending (bool, optional): Whether to sort in ascending order. Defaults to True.

        Returns:
            Self: The query builder instance.
        """
        self.sorts.append(SortColumn(column=column, ascending=ascending))
        return self