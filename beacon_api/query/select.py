from dataclasses import dataclass
from .node import QueryNode

# Ensure compatibility with Python 3.11+ for Self type
try:
    from typing import Optional
    from typing import List
    from typing import Union
except ImportError:
    from typing_extensions import Optional
    from typing_extensions import List
    from typing_extensions import Union

@dataclass
class Select(QueryNode):
    pass

@dataclass
class SelectColumn(Select):
    column: str
    alias: Optional[str] = None

@dataclass
class SelectFunction(Select):
    function: str
    args: Optional[List[Select]] = None
    alias: Optional[str] = None

@dataclass
class SelectLiteral(Select):
    value: Union[str, int, float, bool, None]
    alias: Optional[str] = None
