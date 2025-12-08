from .node import QueryNode as QueryNode
from dataclasses import dataclass
from typing_extensions import Optional, Union

@dataclass
class Select(QueryNode): ...

@dataclass
class SelectColumn(Select):
    column: str
    alias: Optional[str] = ...

@dataclass
class SelectFunction(Select):
    function: str
    args: Optional[list[Select]] = ...
    alias: Optional[str] = ...

@dataclass
class SelectLiteral(Select):
    value: Union[str, int, float, bool, None]
    alias: Optional[str] = ...
