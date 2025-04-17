from __future__ import annotations
from typing import Dict, Optional, Union
from sqlalchemy import *
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, registry
import pyarrow as pa

mapper_registry = registry()

arrow_alchemy_type = {
    "int8": (Integer,int),
    "int16":(Integer,int),
    "int32": (Integer,int),
    "int64": (Integer,int),
    
    "uint8": (Integer,int),
    "uint16": (Integer,int),
    "uint32": (Integer,int),
    "uint64": (Integer,int),
    
    "float16": (Float,float),
    "float32": (Float,float),
    "float64": (Float,float),
    
    "utf8": (String, str),
    "binary": (LargeBinary, bytes),
    "boolean": (Boolean, bool),
}

# SQLAlchemy base class
class QueryableDataTable(DeclarativeBase):
    pass

def replacer(node):
    if isinstance(node, Table) and hasattr(node, "entity_namespace"):
        model = node.entity_namespace
        return getattr(model, "__tvf__", node)  # use __tvf__ if present, else original
    return node

def build_data_table(table_name: str,schema_json: str) -> type:
    if table_name in QueryableDataTable.metadata.tables:
        QueryableDataTable.metadata.remove(QueryableDataTable.metadata.tables[table_name])
    
    
    # Dynamically build attributes for the ORM class
    attrs = {"__tablename__": table_name}
    attrs['_stub'] = Column(Integer, nullable=True, primary_key=True)

    for field in schema_json["fields"]:
        name = field["name"]
        
        dtype = field["data_type"]
        nullable = field.get("nullable", True)
        
        if isinstance(dtype, str):
            dtype = dtype.lower()
            (col_type, py_type) = arrow_alchemy_type[dtype]
        elif isinstance(dtype, dict) and "Timestamp" in dtype:
            col_type = DateTime
            py_type = "datetime.datetime"
        else:
            col_type = String
            py_type = str
        
        
        # Add type hint for autocomplete (e.g., in VSCode or PyCharm)
        attrs[name] = Column(col_type, nullable=nullable)

    new_class = type(table_name, (QueryableDataTable,), attrs)
    return new_class