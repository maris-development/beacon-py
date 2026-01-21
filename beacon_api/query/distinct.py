
from dataclasses import dataclass
from .node import QueryNode

@dataclass
class Distinct(QueryNode):
    columns: list[str]
    
    def to_dict(self) -> dict:
        return {
            "on": self.columns,
            "select": self.columns
        }