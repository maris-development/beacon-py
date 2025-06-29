from __future__ import annotations
import datetime
from typing import Dict, Optional, Union
import pyarrow as pa
from requests import Session

from beacon_api.query import AndFilter, Query, RangeFilter

arrow_py_type = {
    "int8": int,
    "int16": int,
    "int32": int,
    "int64": int,

    "uint8": int,
    "uint16": int,
    "uint32": int,
    "uint64": int,

    "float16": float,
    "float32": float,
    "float64": float,

    "utf8": str,
    "binary": bytes,
    "boolean": bool,
    
    "timestamp[s]": datetime,
    "timestamp[ms]": datetime,
    "timestamp[us]": datetime,
    "timestamp[ns]": datetime,
}


class DataTable:
    # Constructor for DataTable
    def __init__(self, http_session: Session, table_name: str):
        self.http_session = http_session
        self.table_name = table_name
        
        # Now query the server for the table type and description
        # api/table-config?table_name={table_name}
        response = self.http_session.get("/api/table-config", params={"table_name": table_name})
        if response.status_code != 200:
            raise Exception(f"Failed to get table config: {response.text}")
        table_config = response.json()
        self.table_type = table_config.get("type", "unknown")
        self.description = table_config.get("description", None)

    def get_table_description(self) -> str:
        """Get the description of the table"""
        return self.description if self.description else "No description available"    
    
    def get_table_schema(self) -> Dict[str, type]:
        """Get the schema of the table"""
        pa_schema = self.get_table_schema_arrow()
        if pa_schema:
            schema_dict = pa_schema
            return schema_dict
        else:
            raise Exception("Failed to retrieve table schema")

    def get_table_schema_arrow(self) -> pa.Schema:
        """Get the schema of the table in Arrow format"""
        response = self.http_session.get("/api/table-schema", params={"table_name": self.table_name})
        
        if response.status_code != 200:
            raise Exception(f"Failed to get table schema: {response.text}")
        
        schema_data = response.json()
        fields = []
        
        for field in schema_data['fields']:
            field_type = field['data_type']
            
            if isinstance(field_type, str):
                fields.append(pa.field(field['name'], field_type))
            
            elif isinstance(field_type, dict) and field_type.get("Timestamp") == ["Second", None]:
                fields.append(pa.field(field['name'], pa.timestamp('s')))
            elif isinstance(field_type, dict) and field_type.get("Timestamp") == ["Millisecond", None]:
                fields.append(pa.field(field['name'], pa.timestamp('ms')))
            elif isinstance(field_type, dict) and field_type.get("Timestamp") == ["Microsecond", None]:
                fields.append(pa.field(field['name'], pa.timestamp('us')))
            elif isinstance(field_type, dict) and field_type.get("Timestamp") == ["Nanosecond", None]:
                fields.append(pa.field(field['name'], pa.timestamp('ns')))
            
            else:
                raise Exception(f"Unsupported data type for field {field['name']}: {field_type}")
            
        
        return pa.schema(fields)
    
    def get_table_type(self) -> dict:
        """Get the type of the table"""
        return self.table_type
    
    def peek(self, longitude_column: str, latitude_column: str, time_column: str, depth_column: str, columns: list[str],
                         bbox: Optional[tuple[float, float, float, float]] = None,
                         depth_range: Optional[tuple[float, float]] = None,
                         time_range: Optional[tuple[datetime.datetime, datetime.datetime]] = None) -> Query:
        query = self.query()
        query.add_select_column(longitude_column)
        query.add_select_column(latitude_column)
        query.add_select_column(time_column)
        query.add_select_column(depth_column)
        for column in columns:
            query.add_select_column(column)
        if bbox:
            query.add_filter(AndFilter([
                RangeFilter(longitude_column, bbox[0], bbox[2]),
                RangeFilter(latitude_column, bbox[1], bbox[3])
            ]))
        if depth_range:
            query.add_filter(RangeFilter(depth_column, depth_range[0], depth_range[1]))
        if time_range:
            query.add_filter(RangeFilter(time_column, time_range[0].strftime("%Y-%m-%dT%H:%M:%S"), time_range[1].strftime("%Y-%m-%dT%H:%M:%S")))
        return query

    def query(self) -> Query:
        return Query(self.http_session, self.table_name)
