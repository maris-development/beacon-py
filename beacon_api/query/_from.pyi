from .node import QueryNode as QueryNode
from dataclasses import dataclass

class From(QueryNode): ...
class DatasetFormat(QueryNode): ...

@dataclass
class FromTable(From):
    table: str
    def to_dict(self) -> dict: ...

@dataclass
class FromBBFDataset(From):
    paths: list[str]
    def to_dict(self) -> dict: ...

@dataclass
class FromParquetDataset(From):
    paths: list[str]
    def to_dict(self) -> dict: ...

@dataclass
class FromArrowDataset(From):
    paths: list[str]
    def to_dict(self) -> dict: ...

@dataclass
class FromNetCDFDataset(From):
    paths: list[str]
    def to_dict(self) -> dict: ...

@dataclass
class FromCSVDataset(From):
    paths: list[str]
    delimiter: str = ...
    def to_dict(self) -> dict: ...

@dataclass
class FromZarrDataset(From):
    paths: list[str]
    statistics_columns: list[str] | None = ...
    def to_dict(self) -> dict: ...
