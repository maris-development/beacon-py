from .node import QueryNode as QueryNode
from dataclasses import dataclass
from typing_extensions import Optional

@dataclass
class Output(QueryNode): ...

@dataclass
class NetCDF(Output):
    def to_dict(self) -> dict: ...

@dataclass
class NdNetCDF(Output):
    dimension_columns: list[str]
    def to_dict(self) -> dict: ...

@dataclass
class Arrow(Output):
    def to_dict(self) -> dict: ...

@dataclass
class Parquet(Output):
    def to_dict(self) -> dict: ...

@dataclass
class GeoParquet(Output):
    longitude_column: str
    latitude_column: str
    def to_dict(self) -> dict: ...

@dataclass
class CSV(Output):
    def to_dict(self) -> dict: ...

@dataclass
class OdvDataColumn(QueryNode):
    column_name: str
    qf_column: Optional[str] = ...
    comment: Optional[str] = ...
    unit: Optional[str] = ...

@dataclass
class Odv(Output):
    longitude_column: OdvDataColumn
    latitude_column: OdvDataColumn
    time_column: OdvDataColumn
    depth_column: OdvDataColumn
    data_columns: list[OdvDataColumn]
    metadata_columns: list[OdvDataColumn]
    qf_schema: str
    key_column: str
    feature_type_column: Optional[str] = ...
    def to_dict(self) -> dict: ...
