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
from lonboard import Map
from lonboard import viz
from lonboard.basemap import CartoBasemap
from lonboard.colormap import apply_continuous_cmap
from palettable.palette import Palette
from palettable.matplotlib import Viridis_10


from .session import BaseBeaconSession

# Ensure compatibility with Python 3.11+ for Self type
try:
    from typing import Self
    from typing import Literal
except ImportError:
    from typing_extensions import Self
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
    args: list[QueryNode] | None = None
    alias: str | None = None


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
        self.set_output(Arrow())
        response = self.run()

        with open(filename, "wb") as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_parquet(self, filename: str):
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
            
    def to_lonboard_map(
        self,
        longitude: str,
        latitude: str,
        value_column: str,
        crs: str = "EPSG:4326",
        zoom: int = 2,
        color_palette : Palette = Viridis_10,
        radius_units: Literal['meters', 'pixels', 'common'] = 'common',
        radius_scale: float = 10.0,
        radius_min_pixels: int = 5,
        radius_max_pixels: int = 20,
        basemap_style: CartoBasemap = CartoBasemap.Positron,
        show_tooltip: bool = True,
        show_side_panel: bool = True,
    ) -> Map:
        """Visualize the data on a map using lonboard"""
        # Get the data as a GeoDataFrame
        df = self.to_geo_pandas_dataframe(longitude, latitude, crs)
        if df.empty:
            raise ValueError("DataFrame is empty. Cannot visualize on map.")
        
        if crs != "EPSG:4326":
            print(f"Converting GeoDataFrame from {crs} to EPSG:4326")
            df = df.to_crs(epsg=4326)
            
        # Create a lonboard map
        center_lon = df.geometry.x.mean()
        center_lat = df.geometry.y.mean()

        min_value = df[value_column].min()
        max_value = df[value_column].max()
        values = df[value_column].to_numpy()
        normalized_values = (values - min_value) / (max_value - min_value)
        fill_color = apply_continuous_cmap(normalized_values, Viridis_10, alpha=0.8)

        m = viz(
            df,
            scatterplot_kwargs={
                "get_fill_color": fill_color,
                "radius_units": radius_units,
                "radius_scale": radius_scale,
                "radius_min_pixels": radius_min_pixels,
                "radius_max_pixels": radius_max_pixels,
            },
            # choose a nice basemap and initial view
            map_kwargs={
                "show_tooltip": show_tooltip,
                "show_side_panel": show_side_panel,
                "basemap_style": basemap_style,
                "view_state": {
                    "longitude": center_lon,
                    "latitude": center_lat,
                    "zoom": zoom
                },
            },
        )

        return m
