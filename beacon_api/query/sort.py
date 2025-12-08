from dataclasses import dataclass
from .node import QueryNode


@dataclass
class SortColumn(QueryNode):
    column: str
    ascending: bool = True
    
    def to_dict(self) -> dict:
        if self.ascending:
            return { "asc": self.column }
        else:
            return { "desc": self.column }

@dataclass
class Sort(QueryNode):
    columns: list[SortColumn]
    
    def to_dict(self) -> dict:
        return {
            "sort": [
                col.to_dict() for col in self.columns
            ]
        }
