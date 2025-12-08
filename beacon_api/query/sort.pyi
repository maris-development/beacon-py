from .node import QueryNode as QueryNode
from dataclasses import dataclass

@dataclass
class SortColumn(QueryNode):
    column: str
    ascending: bool = ...
    def to_dict(self) -> dict: ...

@dataclass
class Sort(QueryNode):
    columns: list[SortColumn]
    def to_dict(self) -> dict: ...
