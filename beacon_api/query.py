from dataclasses import dataclass, asdict
from datetime import datetime
from io import BytesIO
import json
import networkx as nx
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pyarrow import parquet as pq
from requests import Response
import numpy as np
from numpy.typing import DTypeLike

from .session import BaseBeaconSession

# Ensure compatibility with Python 3.11+ for Self type
try:
    from typing import Self, cast
    from typing import Literal
    from typing import Optional
    from typing import List
    from typing import Union
    from typing import Tuple
except ImportError:
    from typing_extensions import Self, cast
    from typing_extensions import Literal
    from typing_extensions import Optional
    from typing_extensions import List
    from typing_extensions import Union
    from typing_extensions import Tuple


@dataclass
class QueryNode:
    def to_dict(self) -> dict:
        # asdict(self) walks nested dataclasses too
        return asdict(self)


@dataclass
class Select(QueryNode):
    pass


@dataclass
class SelectColumn(Select):
    column: str
    alias: Optional[str] = None


@dataclass
class SelectFunction(Select):
    function: str
    args: Optional[List[Select]] = None
    alias: Optional[str] = None


### PREDEFINED FUNCTIONS ###
class Functions:
    @staticmethod
    def concat(args: List[Union[str, Select]], alias: str) -> SelectFunction:
        """
        Constructs a CONCAT function, concatenating the selected columns or arguments.
        Args:
            args (list[str  |  Select]): List of column names (str) or Select objects to concatenate.
            alias (str): Alias name for the resulting select expression.
        """
        
        select_args = []
        for arg in args:
            if isinstance(arg, str):
                select_args.append(SelectColumn(column=arg))
            elif isinstance(arg, Select):
                select_args.append(arg)
        return SelectFunction("concat", args=select_args, alias=alias)
    
    @staticmethod
    def coalesce(args: List[Union[str, Select]], alias: str) -> SelectFunction:
        """
        Constructs a COALESCE function, returning the first non-null value from the selected columns or arguments.
        Args:
            args (list[str  |  Select]): List of column names (str) or Select objects to coalesce.
            alias (str): Alias name for the resulting select expression.

        Returns:
            SelectFunction: SelectFunction representing the COALESCE operation.
        """
        select_args = []
        for arg in args:
            if isinstance(arg, str):
                select_args.append(SelectColumn(column=arg))
            elif isinstance(arg, Select):
                select_args.append(arg)
        return SelectFunction("coalesce", args=select_args, alias=alias)
    
    @staticmethod
    def try_cast_to_type(arg: Union[str, Select], to_type: DTypeLike, alias: str) -> SelectFunction:
            """
            Attempts to cast the input column or argument to the specified data type.
            Args:
                arg: Column name (str) or Select object to cast.
                to_type: Target data type (compatible with numpy dtype). Eg. np.int64, np.float64, np.datetime64, np.str_
                alias: Alias name for the resulting select expression.
            Returns:
                SelectFunction representing the cast operation.
            """
            dtype = np.dtype(to_type)  # normalize everything into a np.dtype
            arrow_type = None
            if np.issubdtype(dtype, np.integer):
                print("This is an integer dtype:", dtype)
                arrow_type = "Int64"
            elif np.issubdtype(dtype, np.floating):
                arrow_type = "Float64"
            elif np.issubdtype(dtype, np.datetime64):
                arrow_type = 'Timestamp(Nanosecond, None)'
            elif np.issubdtype(dtype, np.str_):
                arrow_type = 'Utf8'
            else:
                raise ValueError(f"Unsupported type for cast_to_type: {to_type}")
            
            if isinstance(arg, str):
                arg = SelectColumn(column=arg)
                return SelectFunction("try_arrow_cast", args=[arg, SelectLiteral(value=arrow_type)], alias=alias)
            elif isinstance(arg, Select):
                return SelectFunction("try_arrow_cast", args=[arg, SelectLiteral(value=arrow_type)], alias=alias)
        
    @staticmethod
    def cast_byte_to_char(arg: Union[str, Select], alias: str) -> SelectFunction:
        """Maps byte values to char.

        Args:
            arg (str | Select): column name (str) or Select object containing the byte value.
            alias (str): Alias name for the resulting select expression/column.

        Returns:
            SelectFunction: SelectFunction representing the cast operation.
        """
        if isinstance(arg, str):
            arg = SelectColumn(column=arg)
        return SelectFunction("cast_int8_as_char", args=[arg], alias=alias)

    @staticmethod
    def map_wod_quality_flag_to_sdn_scheme(arg: Union[str, Select], alias: str) -> SelectFunction:
        """Maps WOD quality flags to the SDN scheme.

        Args:
            arg (str | Select): column name (str) or Select object containing the WOD quality flag.
            alias (str): Alias name for the resulting select expression/column.

        Returns:
            SelectFunction: SelectFunction representing the mapping operation.
        """
        if isinstance(arg, str):
            arg = SelectColumn(column=arg)
        return SelectFunction("map_wod_quality_flag", args=[arg], alias=alias)

    @staticmethod
    def map_pressure_to_depth(arg: Union[str, Select], latitude_column: Union[str, Select], alias: str) -> SelectFunction:
        """Maps pressure values to depth based on latitude using teos-10.

        Args:
            arg (str | Select): column name (str) or Select object containing the pressure value.
            latitude_column (str | Select): column name (str) or Select object containing the latitude value.
            alias (str): Alias name for the resulting select expression/column.

        Returns:
            SelectFunction: SelectFunction representing the pressure-to-depth mapping operation.
        """
        if isinstance(arg, str):
            arg = SelectColumn(column=arg)
        if isinstance(latitude_column, str):
            latitude_column = SelectColumn(column=latitude_column)
        return SelectFunction("pressure_to_depth_teos_10", args=[arg, latitude_column], alias=alias)

### END PREDEFINED FUNCTIONS ###

@dataclass
class SelectLiteral(Select):
    value: Union[str, int, float, bool]
    alias: Optional[str] = None


@dataclass
class Filter(QueryNode):
    pass


@dataclass
class RangeFilter(Filter):
    column: str
    gt_eq: Union[str, int, float, datetime, None] = None
    lt_eq: Union[str, int, float, datetime, None] = None

@dataclass
class EqualsFilter(Filter):
    column: str
    eq: Union[str, int, float, bool, datetime]


@dataclass
class NotEqualsFilter(Filter):
    column: str
    neq: Union[str, int, float, bool, datetime]


@dataclass
class FilterIsNull(Filter):
    column: str

    def to_dict(self) -> dict:
        return {"is_null": {"column": self.column}}


@dataclass
class IsNotNullFilter(Filter):
    column: str

    def to_dict(self) -> dict:
        return {"is_not_null": {"column": self.column}}


@dataclass
class AndFilter(Filter):
    filters: List[Filter]

    def to_dict(self) -> dict:
        return {"and": [f.to_dict() for f in self.filters]}


@dataclass
class OrFilter(Filter):
    filters: List[Filter]

    def to_dict(self) -> dict:
        return {"or": [f.to_dict() for f in self.filters]}

@dataclass
class PolygonFilter(Filter):
    longitude_column: str
    latitude_column: str
    polygon: List[Tuple[float, float]]

    def to_dict(self) -> dict:
        return {
            "longitude_query_parameter": self.longitude_column,
            "latitude_query_parameter": self.latitude_column,
            "geometry": { "coordinates": [self.polygon], "type": "Polygon" }
        }

@dataclass
class Output(QueryNode):
    pass


@dataclass
class NetCDF(Output):
    def to_dict(self) -> dict:
        return {"format": "netcdf"}


@dataclass
class Arrow(Output):
    def to_dict(self) -> dict:
        return {"format": "arrow"}


@dataclass
class Parquet(Output):
    def to_dict(self) -> dict:
        return {"format": "parquet"}


@dataclass
class GeoParquet(Output):
    longitude_column: str
    latitude_column: str

    def to_dict(self) -> dict:
        return {
            "format": {
                "geoparquet": {"longitude_column": self.longitude_column, "latitude_column": self.latitude_column}
            },
        }


@dataclass
class CSV(Output):
    def to_dict(self) -> dict:
        return {"format": "csv"}


@dataclass
class OdvDataColumn(QueryNode):
    column_name: str
    qf_column: Optional[str] = None
    comment: Optional[str] = None
    unit: Optional[str] = None


@dataclass
class Odv(Output):
    """Output format for ODV (Ocean Data View)"""

    longitude_column: OdvDataColumn
    latitude_column: OdvDataColumn
    time_column: OdvDataColumn
    depth_column: OdvDataColumn
    data_columns: List[OdvDataColumn]
    metadata_columns: List[OdvDataColumn]
    qf_schema: str
    key_column: str
    feature_type_column: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "format": {
                "odv": {
                    "longitude_column": self.longitude_column.to_dict(),
                    "latitude_column": self.latitude_column.to_dict(),
                    "time_column": self.time_column.to_dict(),
                    "depth_column": self.depth_column.to_dict(),
                    "data_columns": [col.to_dict() for col in self.data_columns],
                    "metadata_columns": [
                        col.to_dict() for col in self.metadata_columns
                    ],
                    "qf_schema": self.qf_schema,
                    "key_column": self.key_column,
                    "feature_type_column": self.feature_type_column,
                }
            }
        }


class Query:
    def __init__(self, http_session: BaseBeaconSession, from_table: Optional[str] = None, from_file_path: Optional[str] = None):
        """
        A class to build and run Beacon JSON Queries. Best to construct this object using the Client object or Table object.
        """
        self.http_session = http_session
        self.from_table = from_table
        self.from_file_path = from_file_path

    def select(self, selects: List[Select]) -> Self:
        self.selects = selects
        return self

    def add_select(self, select: Select) -> Self:
        if not hasattr(self, "selects"):
            self.selects = []
        self.selects.append(select)
        return self

    def add_selects(self, selects: List[Select]) -> Self:
        """Adds multiple select statements to the query.

        Args:
            selects (list[Select]): The select statements to add.

        Returns:
            Self: The query builder instance.
        """
        if not hasattr(self, "selects"):
            self.selects = []
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
        if not hasattr(self, "selects"):
            self.selects = []
        self.selects.append(SelectColumn(column=column, alias=alias))
        return self

    def add_select_columns(self, columns: List[Tuple[str, Optional[str]]]) -> Self:
        """Adds multiple select columns to the query.

        Args:
            columns (List[Tuple[str, Optional[str]]]): A list of tuples containing column names and their aliases.

        Returns:
            Self: The query builder instance.
        """
        if not hasattr(self, "selects"):
            self.selects = []
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
        if not hasattr(self, "selects"):
            self.selects = []

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
        if not hasattr(self, "filters"):
            self.filters = []
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
            bbox (tuple[float, float, float, float]): The bounding box coordinates (min_lon, max_lon, min_lat, max_lat).

        Returns:
            Self: The query builder instance.
        """
        if not hasattr(self, "filters"):
            self.filters = []
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
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(PolygonFilter(longitude_column=longitude_column, latitude_column=latitude_column, polygon=polygon))
        return self

    def add_range_filter(
        self,
        column: str,
        gt_eq: Union[str, int, float, datetime, None] = None,
        lt_eq: Union[str, int, float, datetime, None] = None,
    ) -> Self:
        """Adds a RANGE filter to the query.

        Args:
            column (str): The name of the column to filter.
            gt_eq (str | int | float | datetime | None, optional): The lower bound for the range filter. Defaults to None.
            lt_eq (str | int | float | datetime | None, optional): The upper bound for the range filter. Defaults to None.

        Returns:
            Self: The query builder instance.
        """
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(RangeFilter(column=column, gt_eq=gt_eq, lt_eq=lt_eq))
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
        if not hasattr(self, "filters"):
            self.filters = []
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

        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(NotEqualsFilter(column=column, neq=neq))
        return self

    def add_is_null_filter(self, column: str) -> Self:
        """Adds an IS NULL filter to the query.

        Args:
            column (str): The name of the column to filter.

        Returns:
            Self: The query builder instance.
        """
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(FilterIsNull(column=column))
        return self

    def add_is_not_null_filter(self, column: str) -> Self:
        """Adds an IS NOT NULL filter to the query.

        Args:
            column (str): The name of the column to filter.

        Returns:
            Self: The query builder instance.
        """
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(IsNotNullFilter(column=column))
        return self

    def set_output(self, output: Output) -> Self:
        """Sets the output format for the query.

        Args:
            output (Output): The output format to use.

        Returns:
            Self: The query builder instance.
        """
        self.output = output
        return self

    def compile_query(self) -> str:
        """Compiles the query into a Beacon JSON Query.

        Raises:
            ValueError: If the query is invalid.
            ValueError: If the query is invalid.
            TypeError: If the query is invalid.
            
        Returns:
            str: The compiled query as a JSON string.
        """
        # Check if from_table is set
        from_ = None
        if not self.from_table and not self.from_file_path:
            from_ = "default"
        elif self.from_table and self.from_file_path:
            raise ValueError("Cannot set both from_table and from_file_path")
        elif self.from_file_path:
            from_ = self.from_file_path
        else:
            from_ = self.from_table

        # Check if output is set
        if not hasattr(self, "output"):
            raise ValueError("Output must be set before compiling the query")

        # Check if selects are set
        if not hasattr(self, "selects"):
            raise ValueError("Selects must be set before compiling the query")

        query = {
            "from": from_,
            "select": (
                [s.to_dict() for s in self.selects] if hasattr(self, "selects") else []
            ),
            "filters": (
                [f.to_dict() for f in self.filters] if hasattr(self, "filters") else []
            ),
            "output": self.output.to_dict() if hasattr(self, "output") else {},
        }

        # Convert datetime objects to ISO format strings
        # This is necessary for JSON serialization
        def datetime_converter(o):
            if isinstance(o, datetime):
                return o.strftime("%Y-%m-%dT%H:%M:%S.%f")
            raise TypeError(f"Type {type(o)} not serializable")

        return json.dumps(query, default=datetime_converter)

    def run(self) -> Response:
        """Run the query and return the response"""
        query = self.compile_query()
        print(f"Running query: {query}")
        response = self.http_session.post("/api/query", data=query)
        if response.status_code != 200:
            raise Exception(f"Query failed: {response.text}")
        if len(response.content) == 0:
            raise Exception("Query returned no content")
        return response

    def explain(self) -> dict:
        """Get the query plan"""
        query = self.compile_query()
        response = self.http_session.post("/api/explain-query", data=query)
        if response.status_code != 200:
            raise Exception(f"Explain query failed: {response.text}")
        return response.json()

    def explain_visualize(self):
        """Visualize the query plan using networkx and matplotlib"""
        
        try: 
            import networkx as nx
            import matplotlib.pyplot as plt
        except ImportError as e:
            raise ImportError(
                "This function requires `networkx` and `matplotlib`. Install with `pip install beacon-api[profiling]`."
            ) from e
        
        plan_json = self.explain()
        # Extract the root plan node
        root_plan = plan_json[0]["Plan"]

        # === Step 2: Build a directed graph ===
        G = nx.DiGraph()

        def make_label(node):
            """Build a multi‐line label from whichever fields are present."""
            parts = [node.get("Node Type", "<unknown>")]
            for field in (
                "File Type",
                "Options",
                "Condition",
                "Output URL",
                "Expressions",
                "Output",
                "Filter",
            ):
                if field in node and node[field]:
                    parts.append(f"{field}: {node[field]}")
            return "\n".join(parts)

        def add_nodes(node, parent_id=None):
            nid = id(node)
            G.add_node(nid, label=make_label(node))
            if parent_id is not None:
                G.add_edge(parent_id, nid)
            for child in node.get("Plans", []):
                add_nodes(child, nid)

        add_nodes(root_plan)

        try:
            pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
        except Exception:
            pos = nx.spring_layout(G)

        plt.figure(figsize=(8, 6))
        labels = nx.get_node_attributes(G, "label")
        nx.draw(G, pos, labels=labels, with_labels=True, node_size=2000, font_size=8)
        plt.title("Beacon Query Plan Visualization")
        plt.tight_layout()
        plt.show()

    def to_netcdf(self, filename: str, build_nc_local: bool = True):
        """Export the query result to a NetCDF file
        Args:
            filename (str): The name of the output NetCDF file.
            build_nc_local (bool): 
                If True, build the NetCDF file locally using pandas and xarray. (This is likely faster in most cases.)
                If False, use the server to build the NetCDF file.
        """
        # If build_nc_local is True, we will build the NetCDF file locally
        if build_nc_local:
            df = self.to_pandas_dataframe()
            xdf = df.to_xarray()
            xdf.to_netcdf(filename, mode="w")
        # If build_nc_local is False, we will use the server to build the NetCDF
        else:
            self.set_output(NetCDF())
            response = self.run()
            with open(filename, "wb") as f:
                # Write the content of the response to a file
                f.write(response.content)  # type: ignore



    def to_arrow(self, filename: str):
        """
        Converts the query result to Apache Arrow format and writes it to a file.

        Args:
            filename (str): The path to the file where the Arrow-formatted data will be saved.

        Returns:
            None

        Side Effects:
            Writes the Arrow-formatted response content to the specified file.
        """
        self.set_output(Arrow())
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_parquet(self, filename: str):
        """
        Exports the query results to a Parquet file.

        This method sets the output format to Parquet, executes the query, and writes the resulting data to the specified file.

        Args:
            filename (str): The path to the file where the Parquet data will be saved.

        Returns:
            None
        """
        self.set_output(Parquet())
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_geoparquet(self, filename: str, longitude_column: str, latitude_column: str):
        """
        Exports the query results to a GeoParquet file.
        
        Args:
            filename (str): The path to the file where the GeoParquet data will be saved.
            longitude_column (str): The name of the column representing longitude.
            latitude_column (str): The name of the column representing latitude.
        """
        self.set_output(GeoParquet(longitude_column=longitude_column, latitude_column=latitude_column))
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_csv(self, filename: str):
        """Exports the query results to a CSV file.

        Args:
            filename (str): The path to the file where the CSV data will be saved.
        """
        self.set_output(CSV())
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_zarr(self, filename: str):
        """Exports the query results to a Zarr file.

        Args:
            filename (str): The path to the file where the Zarr data will be saved.
        """
        
        try:
            import zarr # just to check if zarr is installed
        except ImportError as e:
            raise ImportError(
                "This function requires `zarr`. Install with `pip install beacon-api[zarr]`."
            ) from e
    
        # Read to pandas dataframe first
        df = self.to_pandas_dataframe()
        # Convert to Zarr format
        xdf = df.to_xarray()
        xdf.to_zarr(filename, mode="w")

    def to_pandas_dataframe(self) -> pd.DataFrame:
        """Converts the query results to a pandas DataFrame.

        Returns:
            pd.DataFrame: The query results as a pandas DataFrame.
        """
        self.set_output(Parquet())
        response = self.run()
        bytes_io = BytesIO(response.content)

        df = pd.read_parquet(bytes_io)
        return df

    def to_geo_pandas_dataframe(self, longitude_column: str, latitude_column: str, crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
        """Converts the query results to a GeoPandas GeoDataFrame.

        Args:
            longitude_column (str): The name of the column representing longitude.
            latitude_column (str): The name of the column representing latitude.
            crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:4326".

        Returns:
            gpd.GeoDataFrame: The query results as a GeoPandas GeoDataFrame.
        """
        
        try:
            import geopandas as gpd
        except ImportError as e:
            raise ImportError(
                "This function requires `geopandas`. Install with `pip install beacon-api[geopandas]`."
            ) from e
        
        self.set_output(GeoParquet(longitude_column=longitude_column, latitude_column=latitude_column))
        response = self.run()
        bytes_io = BytesIO(response.content)
        # Read into parquet arrow table 
        table = pq.read_table(bytes_io)
        
        gdf = gpd.GeoDataFrame.from_arrow(table)
        gdf.set_crs(crs, inplace=True)
        return gdf

    def to_odv(self, odv_output: Odv, filename: str):
        """Exports the query results to an ODV file.

        Args:
            odv_output (Odv): The ODV output format to use.
            filename (str): The path to the file where the ODV data will be saved.
        """
        self.set_output(odv_output)
        response = self.run()
        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)
