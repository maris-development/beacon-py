from .node import QueryNode as QueryNode
from dataclasses import dataclass
from datetime import datetime
from typing_extensions import Union

@dataclass
class Filter(QueryNode): ...

@dataclass
class RangeFilter(Filter):
    column: str
    gt_eq: Union[str, int, float, datetime, None] = ...
    lt_eq: Union[str, int, float, datetime, None] = ...

@dataclass
class ExclusiveRangeFilter(Filter):
    column: str
    gt: Union[str, int, float, datetime, None] = ...
    lt: Union[str, int, float, datetime, None] = ...

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
    def to_dict(self) -> dict: ...

@dataclass
class IsNotNullFilter(Filter):
    column: str
    def to_dict(self) -> dict: ...

@dataclass
class AndFilter(Filter):
    filters: list[Filter]
    def to_dict(self) -> dict: ...

@dataclass
class OrFilter(Filter):
    filters: list[Filter]
    def to_dict(self) -> dict: ...

@dataclass
class PolygonFilter(Filter):
    longitude_column: str
    latitude_column: str
    polygon: list[tuple[float, float]]
    def to_dict(self) -> dict: ...
