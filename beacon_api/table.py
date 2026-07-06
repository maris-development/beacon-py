from __future__ import annotations
import datetime
import re
from typing import Optional, Union
import pyarrow as pa
from packaging.version import Version

from .session import BaseBeaconSession
from .query import JSONQuery, SQLQuery, RangeFilter, AndFilter
from .query._from import FromTable

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

# Keyed by the lower-cased unit name so both the full Arrow Debug spelling
# ("Millisecond") and short aliases ("ms", "ns") resolve to the same unit.
_TIMESTAMP_UNITS = {
    "second": "s",
    "millisecond": "ms",
    "microsecond": "us",
    "nanosecond": "ns",
    "s": "s",
    "ms": "ms",
    "us": "us",
    "ns": "ns",
}

# Matches the Arrow Debug representation of a timestamp data type, e.g.
# "Timestamp(Millisecond, None)", "Timestamp(Second, Some(\"UTC\"))" or the
# abbreviated "Timestamp(ns)". The timezone clause is optional and the whole
# match is case-insensitive; the timezone name itself keeps its original case.
_TIMESTAMP_STR_RE = re.compile(
    r'^Timestamp\(\s*(?P<unit>\w+)\s*'
    r'(?:,\s*(?P<tz>None|Some\("(?P<tzname>[^"]*)"\)))?\s*\)$',
    re.IGNORECASE,
)


def _parse_arrow_type(field_type: Union[str, dict]) -> Optional[pa.DataType]:
    """Convert a Beacon schema ``data_type`` into a pyarrow ``DataType``.

    Handles both the dict form ``{"Timestamp": ["Millisecond", None]}`` and the
    string form ``"Timestamp(Millisecond, None)"`` used since the 1.2.0 schema
    change, as well as plain type aliases such as ``"int64"``. Returns ``None``
    when the type is not recognised.
    """
    if isinstance(field_type, dict):
        timestamp = field_type.get("Timestamp")
        if isinstance(timestamp, (list, tuple)) and len(timestamp) == 2:
            unit, tz = timestamp
            pa_unit = _TIMESTAMP_UNITS.get(str(unit).lower())
            if pa_unit is not None:
                return pa.timestamp(pa_unit, tz=tz)
        return None

    if isinstance(field_type, str):
        match = _TIMESTAMP_STR_RE.match(field_type)
        if match:
            pa_unit = _TIMESTAMP_UNITS.get(match.group("unit").lower())
            if pa_unit is not None:
                return pa.timestamp(pa_unit, tz=match.group("tzname"))
            return None
        try:
            return pa.type_for_alias(field_type.lower())
        except ValueError:
            return None

    return None


def _schema_from_rows(names: list, types: list) -> pa.Schema:
    """Build a ``pa.Schema`` from parallel column-name / data-type lists.

    Shared by the SQL ``DESCRIBE <table>`` and ``read_schema(...)`` paths, both
    of which return a column of names and a column of Arrow type spellings.
    """
    fields = []
    for name, data_type in zip(names, types):
        pa_type = _parse_arrow_type(data_type)
        if pa_type is None:
            raise Exception(f"Unsupported data type for field {name}: {data_type}")
        fields.append(pa.field(str(name), pa_type))
    return pa.schema(fields)


def _schema_from_arrow_result(result: pa.Table) -> pa.Schema:
    """Parse a name/type result table (DESCRIBE or read_schema) into a schema."""
    columns = result.column_names
    name_col = "column_name" if "column_name" in columns else columns[0]
    type_col = "data_type" if "data_type" in columns else columns[1]
    return _schema_from_rows(
        result.column(name_col).to_pylist(),
        result.column(type_col).to_pylist(),
    )


def schema_from_describe(http_session: BaseBeaconSession, table_name: str) -> pa.Schema:
    """Resolve a table schema via SQL ``DESCRIBE <table>``.

    Returns the table's columns as a :class:`pyarrow.Schema`. The DESCRIBE result
    exposes ``column_name`` and ``data_type`` columns which are parsed into Arrow
    types via :func:`_parse_arrow_type`.
    """
    result = SQLQuery(http_session=http_session, query=f"DESCRIBE {table_name}").to_arrow_table()
    return _schema_from_arrow_result(result)


def schema_from_read_schema(http_session: BaseBeaconSession, file_path: str, file_format: str) -> pa.Schema:
    """Resolve a dataset schema via the SQL ``read_schema(paths, format)`` table function."""
    sql = f"SELECT * FROM read_schema(['{file_path}'], '{file_format}')"
    result = SQLQuery(http_session=http_session, query=sql).to_arrow_table()
    return _schema_from_arrow_result(result)


class DataTable:
    """Represents a data table available on the Beacon Node."""
    
    # Constructor for DataTable
    def __init__(self, http_session: BaseBeaconSession, table_name: str):
        self.http_session = http_session
        self.table_name = table_name

        # The /api/table-config endpoint only exists on the REST backend. Under
        # the SQL backend there is no equivalent for the table type/description,
        # so we leave them unset and rely on DESCRIBE for the schema.
        if getattr(self.http_session, "backend", "rest") == "sql":
            self.table_type = "unknown"
            self.description = None
            return

        # Now query the server for the table type and description
        # api/table-config?table_name={table_name}
        
        if http_session.beacon_node_version < Version("1.7.0"):
            response = self.http_session.get("/api/table-config", params={"table_name": table_name})
            if response.status_code != 200:
                raise Exception(f"Failed to get table config: {response.text}")
            table_config = response.json()
            self.table_type = table_config.get("table_type", "unknown")
            self.description = table_config.get("description", None)
        else:
            self.table_type = "unknown"
            self.description = None

    def get_table_description(self) -> str:
        """Get the description of the table"""
        return self.description if self.description else "No description available"    
    
    def get_table_schema(self) -> dict[str, type]:
        """Get the schema of the table"""
        pa_schema = self.get_table_schema_arrow()
        if pa_schema:
            schema_dict = pa_schema
            return schema_dict
        else:
            raise Exception("Failed to retrieve table schema")

    def get_table_schema_arrow(self) -> pa.Schema:
        """Get the schema of the table in Arrow format"""
        # SQL backend: resolve the schema via DESCRIBE <table>.
        if getattr(self.http_session, "backend", "rest") == "sql":
            return schema_from_describe(self.http_session, self.table_name)

        response = self.http_session.get("/api/table-schema", params={"table_name": self.table_name})

        if response.status_code != 200:
            raise Exception(f"Failed to get table schema: {response.text}")
        
        schema_data = response.json()
        fields = []

        for field in schema_data['fields']:
            pa_type = _parse_arrow_type(field['data_type'])
            if pa_type is None:
                raise Exception(f"Unsupported data type for field {field['name']}: {field['data_type']}")
            fields.append(pa.field(field['name'], pa_type))

        return pa.schema(fields)
    
    def get_table_type(self) -> Union[dict, str]:
        """Get the type of the table"""
        return self.table_type
    
    
    def subset(self, longitude_column: str, latitude_column: str, time_column: str, depth_column: str, columns: list[str],
                         bbox: Optional[tuple[float, float, float, float]] = None,
                         depth_range: Optional[tuple[float, float]] = None,
                         time_range: Optional[tuple[datetime.datetime, datetime.datetime]] = None) -> JSONQuery:
        """
        Create a query to subset the table based on the provided parameters.
        
        Args:
            longitude_column: Name of the column containing longitude values.
            latitude_column: Name of the column containing latitude values.
            time_column: Name of the column containing time values.
            depth_column: Name of the column containing depth values.
            columns: List of additional columns to include in the query.
            bbox: Optional bounding box defined as (min_longitude, min_latitude, max_longitude, max_latitude).
            depth_range: Optional range for depth defined as (min_depth, max_depth).
            time_range: Optional range for time defined as (start_time, end_time).
        Returns
            A Query object that can be executed to retrieve the subset of data.
        """
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

    def query(self) -> JSONQuery:
        """Create a new query for the selected table.
        The query can then be built using the Query methods.
        Returns:
            JSONQuery: A new query object.
        """
        return JSONQuery(self.http_session, _from=FromTable(self.table_name))