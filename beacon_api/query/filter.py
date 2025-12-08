
from dataclasses import dataclass
from datetime import datetime
from .node import QueryNode

# Ensure compatibility with Python 3.11+ for Self type
try:
    from typing import Optional
    from typing import List
    from typing import Union
    from typing import Tuple
except ImportError:
    from typing_extensions import Optional
    from typing_extensions import List
    from typing_extensions import Union
    from typing_extensions import Tuple

@dataclass
class Filter(QueryNode):
    pass

@dataclass
class RangeFilter(Filter):
    column: str
    gt_eq: Union[str, int, float, datetime, None] = None
    lt_eq: Union[str, int, float, datetime, None] = None

@dataclass
class ExclusiveRangeFilter(Filter):
    column: str
    gt: Union[str, int, float, datetime, None] = None
    lt: Union[str, int, float, datetime, None] = None

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
