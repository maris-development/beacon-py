from dataclasses import dataclass, asdict
from datetime import datetime
from io import BytesIO
import json
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
from requests import Response, Session
from typing import Self

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
    function_name: str
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
        return {
            "is_null": {
                "column": self.column
            }
        }
    
@dataclass
class IsNotNullFilter(Filter):
    column: str
    
    def to_dict(self) -> dict:
        return {
            "is_not_null": {
                "column": self.column
            }
        }
        
@dataclass
class AndFilter(Filter):
    filters: list[Filter]
    
    def to_dict(self) -> dict:
        return {
            "and": [f.to_dict() for f in self.filters]
        }

@dataclass
class OrFilter(Filter):
    filters: list[Filter]

    def to_dict(self) -> dict:
        return {
            "or": [f.to_dict() for f in self.filters]
        }

@dataclass
class Output(QueryNode):
    pass

@dataclass
class NetCDF(Output):
    def to_dict(self) -> dict:
        return {
            "format": "netcdf"
        }



@dataclass
class Arrow(Output):
    def to_dict(self) -> dict:
        return {
            "format": "arrow"
        }

@dataclass
class Parquet(Output):
    def to_dict(self) -> dict:
        return {
            "format": "parquet"
        }

@dataclass
class GeoParquet(Output):
    longtitude: str
    latitude: str
    
    def to_dict(self) -> dict:
        return {
            "format": {
                "geoparquet": {
                    "longtitude": self.longtitude,
                    "latitude": self.latitude
                }
            },
        }
    
@dataclass
class CSV(Output):
    def to_dict(self) -> dict:
        return {
            "format": "csv"
        }

class Query:
    def __init__(self, http_session: Session, from_table: str | None = None):
        self.http_session = http_session
        self.from_table = from_table

    def select(self, selects: list[Select]) -> Self:
        self.selects = selects
        return self
    
    def add_select(self, select: Select) -> Self:
        if not hasattr(self, 'selects'):
            self.selects = []
        self.selects.append(select)
        return self

    def add_select_column(self, column: str, alias: str | None = None) -> Self:
        if not hasattr(self, 'selects'):
            self.selects = []
        self.selects.append(SelectColumn(column=column, alias=alias))
        return self

    def filter(self, filters: list[Filter]) -> Self:
        self.filters = filters
        return self
        
    def add_filter(self, filter: Filter) -> Self:
        if not hasattr(self, 'filters'):
            self.filters = []
        self.filters.append(filter)
        return self
        
    def set_output(self, output: Output) -> Self: 
        self.output = output
        return self

    def compile_query(self) -> str:
        # Check if from_table is set
        if not self.from_table:
            raise ValueError("from_table must be set before compiling the query")
        
        # Check if output is set
        if not hasattr(self, 'output'):
            raise ValueError("Output must be set before compiling the query")
        
        # Check if selects are set
        if not hasattr(self, 'selects'):
            raise ValueError("Selects must be set before compiling the query")
        
        query = {
            "from": self.from_table,
            "select": [s.to_dict() for s in self.selects] if hasattr(self, 'selects') else [],
            "filters": [f.to_dict() for f in self.filters] if hasattr(self, 'filters') else [],
            "output": self.output.to_dict() if hasattr(self, 'output') else { }
        }
        return json.dumps(query)

    def run(self) -> Response:
        query = self.compile_query()
        response = self.http_session.post("/api/query", data=query)
        if response.status_code != 200:
            raise Exception(f"Query failed: {response.text}")
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
        root_plan = plan_json[0]['Plan']

        # === Step 2: Build a directed graph ===
        G = nx.DiGraph()
        
        def make_label(node):
            """Build a multi‐line label from whichever fields are present."""
            parts = [node.get('Node Type', '<unknown>')]
            for field in ('File Type','Options','Condition','Output URL', 'Expressions', 'Output', 'Filter'):
                if field in node and node[field]:
                    parts.append(f"{field}: {node[field]}")
            return "\n".join(parts)

        def add_nodes(node, parent_id=None):
            nid = id(node)
            G.add_node(nid, label=make_label(node))
            if parent_id is not None:
                G.add_edge(parent_id, nid)
            for child in node.get('Plans', []):
                add_nodes(child, nid)

        add_nodes(root_plan)
        
        try:
            pos = nx.nx_agraph.graphviz_layout(G, prog='dot')
        except Exception:
            pos = nx.spring_layout(G)
            
        plt.figure(figsize=(8, 6))
        labels = nx.get_node_attributes(G, 'label')
        nx.draw(G, pos, labels=labels, with_labels=True, node_size=2000, font_size=8)
        plt.title('Beacon Query Plan Visualization')
        plt.tight_layout()
        plt.show()
        
    def to_netcdf(self, filename: str):
        self.set_output(NetCDF())
        response = self.run()
        
        with open(filename, 'w') as f:
            # Write the content of the response to a file
            f.write(response.content) # type: ignore
    
    def to_arrow(self, filename: str):
        self.set_output(Arrow())
        response = self.run()
        
        with open(filename, 'wb') as f:
            # Write the content of the response to a file
            f.write(response.content)
    
    def to_parquet(self, filename: str):
        self.set_output(Parquet())
        response = self.run()
        
        with open(filename, 'wb') as f:
            # Write the content of the response to a file
            f.write(response.content)
    
    def to_geoparquet(self, filename: str, longtitude: str, latitude: str):
        self.set_output(GeoParquet(longtitude=longtitude, latitude=latitude))
        response = self.run()

        with open(filename, 'wb') as f:
            # Write the content of the response to a file
            f.write(response.content)

    def to_csv(self, filename: str):
        self.set_output(CSV())
        response = self.run()

        with open(filename, 'wb') as f:
            # Write the content of the response to a file
            f.write(response.content)
    
    def to_pandas_dataframe(self) -> pd.DataFrame:
        self.set_output(Parquet())
        response = self.run()
        bytes_io = BytesIO(response.content)
        
        df = pd.read_parquet(bytes_io)
        return df
    
    def to_geo_pandas_dataframe(self, longtitude: str, latitude: str):
        self.set_output(GeoParquet(longtitude=longtitude, latitude=latitude))
        response = self.run()
        bytes_io = BytesIO(response.content)
        df = pd.read_parquet(bytes_io)
        # Convert to GeoDataFrame
        try:
            import geopandas as gpd
            gdf = gpd.GeoDataFrame(df)
            return gdf
        except ImportError:
            raise ImportError("geopandas is not installed. Please install it to use this method.")
    

