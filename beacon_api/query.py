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
except ImportError:
    from typing_extensions import Self, cast
    from typing_extensions import Literal


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
    alias: str | None = None


@dataclass
class SelectFunction(Select):
    function: str
    args: list[Select] | None = None
    alias: str | None = None


### PREDEFINED FUNCTIONS ###
class Functions:
    @staticmethod
    def coalesce(args: list[str | Select], alias: str) -> SelectFunction:
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
    def try_cast_to_type(arg: str | Select, to_type: DTypeLike, alias: str) -> SelectFunction:
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
    def cast_byte_to_char(arg: str | Select, alias: str) -> SelectFunction:
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
    def map_wod_quality_flag_to_sdn_scheme(arg: str | Select, alias: str) -> SelectFunction:
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
    def map_pressure_to_depth(arg: str | Select, latitude_column: str | Select, alias: str) -> SelectFunction:
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
        return SelectFunction("map_pressure_to_depth", args=[arg, latitude_column], alias=alias)

### END PREDEFINED FUNCTIONS ###

@dataclass
class SelectLiteral(Select):
    value: str | int | float | bool
    alias: str | None = None


@dataclass
class Filter(QueryNode):
    pass


@dataclass
class RangeFilter(Filter):
    column: str
    gt_eq: str | int | float | datetime | None = None
    lt_eq: str | int | float | datetime | None = None

@dataclass
class EqualsFilter(Filter):
    column: str
    eq: str | int | float | bool | datetime


@dataclass
class NotEqualsFilter(Filter):
    column: str
    neq: str | int | float | bool | datetime


@dataclass
class FilerIsNull(Filter):
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
    filters: list[Filter]

    def to_dict(self) -> dict:
        return {"and": [f.to_dict() for f in self.filters]}


@dataclass
class OrFilter(Filter):
    filters: list[Filter]

    def to_dict(self) -> dict:
        return {"or": [f.to_dict() for f in self.filters]}

@dataclass
class PolygonFilter(Filter):
    longitude_column: str
    latitude_column: str
    polygon: list[tuple[float, float]]

    def to_dict(self) -> dict:
        return {
            "longitude_query_parameter": self.longitude_column,
            "latitude_query_parameter": self.latitude_column,
            "geometry": { "coordinates": self.polygon, "type": "Polygon" }
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
    qf_column: str | None = None
    comment: str | None = None
    unit: str | None = None


@dataclass
class Odv(Output):
    """Output format for ODV (Ocean Data View)"""

    longitude_column: OdvDataColumn
    latitude_column: OdvDataColumn
    time_column: OdvDataColumn
    depth_column: OdvDataColumn
    data_columns: list[OdvDataColumn]
    metadata_columns: list[OdvDataColumn]
    qf_schema: str
    key_column: str
    archiving: str = "zip_deflate"

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
                    "archiving": self.archiving,
                }
            }
        }


class Query:
    def __init__(self, http_session: BaseBeaconSession, from_table: str | None = None):
        self.http_session = http_session
        self.from_table = from_table

    def select(self, selects: list[Select]) -> Self:
        self.selects = selects
        return self

    def add_select(self, select: Select) -> Self:
        if not hasattr(self, "selects"):
            self.selects = []
        self.selects.append(select)
        return self

    def add_selects(self, selects: list[Select]) -> Self:
        if not hasattr(self, "selects"):
            self.selects = []
        self.selects.extend(selects)
        return self

    def add_select_column(self, column: str, alias: str | None = None) -> Self:
        if not hasattr(self, "selects"):
            self.selects = []
        self.selects.append(SelectColumn(column=column, alias=alias))
        return self

    def add_select_columns(self, columns: list[tuple[str, str | None]]) -> Self:
        if not hasattr(self, "selects"):
            self.selects = []
        for column, alias in columns:
            self.selects.append(SelectColumn(column=column, alias=alias))
        return self
    
    def add_select_coalesced(self, mergeable_columns: list[str], alias: str) -> Self:
        if not hasattr(self, "selects"):
            self.selects = []
        
        function_call = SelectFunction("coalesce", args=[SelectColumn(column=col) for col in mergeable_columns], alias=alias)
        self.selects.append(function_call)
        return self

    def filter(self, filters: list[Filter]) -> Self:
        self.filters = filters
        return self

    def add_filter(self, filter: Filter) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(filter)
        return self

    def add_bbox_filter(
        self,
        longitude_column: str,
        latitude_column: str,
        bbox: tuple[float, float, float, float],
    ) -> Self:
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
    
    def add_polygon_filter(self, longitude_column: str, latitude_column: str, polygon: list[tuple[float, float]]) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(PolygonFilter(longitude_column=longitude_column, latitude_column=latitude_column, polygon=polygon))
        return self

    def add_range_filter(
        self,
        column: str,
        gt_eq: str | int | float | datetime | None = None,
        lt_eq: str | int | float | datetime | None = None,
    ) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(RangeFilter(column=column, gt_eq=gt_eq, lt_eq=lt_eq))
        return self

    def add_equals_filter(
        self, column: str, eq: str | int | float | bool | datetime
    ) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(EqualsFilter(column=column, eq=eq))
        return self

    def add_not_equals_filter(
        self, column: str, neq: str | int | float | bool | datetime
    ) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(NotEqualsFilter(column=column, neq=neq))
        return self

    def add_is_null_filter(self, column: str) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(FilerIsNull(column=column))
        return self

    def add_is_not_null_filter(self, column: str) -> Self:
        if not hasattr(self, "filters"):
            self.filters = []
        self.filters.append(IsNotNullFilter(column=column))
        return self

    def set_output(self, output: Output) -> Self:
        self.output = output
        return self

    def compile_query(self) -> str:
        # Check if from_table is set
        if not self.from_table:
            self.from_table = "default"

        # Check if output is set
        if not hasattr(self, "output"):
            raise ValueError("Output must be set before compiling the query")

        # Check if selects are set
        if not hasattr(self, "selects"):
            raise ValueError("Selects must be set before compiling the query")

        query = {
            "from": self.from_table,
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
        self.set_output(GeoParquet(longitude_column=longitude_column, latitude_column=latitude_column))
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_csv(self, filename: str):
        self.set_output(CSV())
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_zarr(self, filename: str):
        # Read to pandas dataframe first
        df = self.to_pandas_dataframe()
        # Convert to Zarr format
        xdf = df.to_xarray()
        xdf.to_zarr(filename, mode="w")

    def to_pandas_dataframe(self) -> pd.DataFrame:
        self.set_output(Parquet())
        response = self.run()
        bytes_io = BytesIO(response.content)

        df = pd.read_parquet(bytes_io)
        return df

    def to_geo_pandas_dataframe(self, longitude_column: str, latitude_column: str, crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
        self.set_output(GeoParquet(longitude_column=longitude_column, latitude_column=latitude_column))
        response = self.run()
        bytes_io = BytesIO(response.content)
        # Read into parquet arrow table 
        table = pq.read_table(bytes_io)
        
        gdf = gpd.GeoDataFrame.from_arrow(table)
        gdf.set_crs(crs, inplace=True)
        return gdf

    def to_odv(self, odv_output: Odv, filename: str):
        self.set_output(odv_output)
        response = self.run()
        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)
