from .node import QueryNode as QueryNode
from dataclasses import dataclass

@dataclass
class Distinct(QueryNode):
    columns: list[str]
    def to_dict(self) -> dict: ...
