from dataclasses import dataclass
from .node import QueryNode

# Ensure compatibility with Python 3.11+ for Self type
try:
    from typing import Optional
    from typing import List
except ImportError:
    from typing_extensions import Optional
    from typing_extensions import List
    
@dataclass
class Output(QueryNode):
    pass

@dataclass
class NetCDF(Output):
    def to_dict(self) -> dict:
        return {"format": "netcdf"}

@dataclass
class NdNetCDF(Output):
    dimension_columns: List[str]
    def to_dict(self) -> dict:
        return {
            "format": {
                "nd_netcdf": {
                    "dimension_columns": self.dimension_columns
                }
            }
        }

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