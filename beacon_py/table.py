from typing import Dict, Optional, Union
from sqlalchemy import *
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from __future__ import annotations
import pyarrow as pa

arrow_type_map = {
    "int8": pa.int8(),
    "int16": pa.int16(),
    "int32": pa.int32(),
    "int64": pa.int64(),
    
    "uint8": pa.uint8(),
    "uint16": pa.uint16(),
    "uint32": pa.uint32(),
    "uint64": pa.uint64(),
    
    "float16": pa.float16(),
    "float32": pa.float32(),
    "float64": pa.float64(),
    
    "string": pa.string(),
    "binary": pa.binary(),
    "bool": pa.bool_(),
    "timestamp_ms": pa.timestamp('ms'),
    "timestamp_ns": pa.timestamp('ns'),
    "timestamp_us": pa.timestamp('us')
}

# Map Arrow Types to Sql Alchemy , and Python types
arrow_sql_alchemy_types = {
    pa.int8() : (Integer,int),
    pa.int16() : (Integer,int),
    pa.int32() : (Integer,int),
    pa.int64() : (BigInteger,int),
    
    pa.uint8() : (Integer,int),
    pa.uint16() : (Integer,int),
    pa.uint32() : (Integer,int),
    pa.uint64() : (BigInteger,int),
    
    pa.float16() : (Float,float),
    pa.float32() : (Float,float),
    pa.float64() : (Float,float),
    
    pa.string() : (String, str),
    pa.binary() : (LargeBinary, bytes),
    pa.bool_() : (Boolean, bool),
    pa.timestamp('ms'): (DateTime, "datetime"),
    pa.timestamp('ns'): (DateTime, "datetime"),
    pa.timestamp('us'): (DateTime, "datetime")
}

# SQLAlchemy base class
class QueryableDataTable(DeclarativeBase):
    pass

def replacer(node):
    if isinstance(node, Table) and hasattr(node, "entity_namespace"):
        model = node.entity_namespace
        return getattr(model, "__tvf__", node)  # use __tvf__ if present, else original
    return node

def build_model_from_json(config: dict):
    table_name = config.get("table")
    function_name = config.get("function")
    file_arg = config.get("file")
    columns = config["columns"]

    attrs = {
        "__annotations__": {},
    }

    column_names = list(columns.keys())

    # Determine which "FROM" source to use
    if table_name:
        attrs["__tablename__"] = table_name
    elif function_name and file_arg:
        tvf = getattr(func, function_name)(file_arg).table_valued(*column_names)
        attrs["__tvf__"] = tvf
        attrs["__tablename__"] = f"{function_name}()"  # for introspection/debug
    else:
        raise ValueError("Must provide either 'table' or both 'function' and 'file'.")

    for col_name, type_str in columns.items():
        sa_type, py_type = arrow_type_map[type_str]
        attrs["__annotations__"][col_name] = Mapped[py_type]
        attrs[col_name] = mapped_column(sa_type)

    table_name = table_name or file_arg.stem
    return type((table_name), (QueryableDataTable,), attrs)