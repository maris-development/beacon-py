from dataclasses import dataclass

@dataclass
class QueryNode:
    def to_dict(self) -> dict: ...
