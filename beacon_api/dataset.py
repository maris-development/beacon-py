"""Dataset helper utilities used throughout the public Beacon Python SDK.

This module provides the :class:`Dataset` façade, which combines a Beacon session
with file metadata so users can introspect schemas and immediately start building
:class:`~beacon_api.query.JSONQuery` instances. The public API mirrors the
documentation shipped with the SDK to ensure editors and tooling surface the
same narrative found in the docs site.
"""

from __future__ import annotations
import pyarrow as pa
import os
from typing import Any, Callable, Dict, Generic, Literal, Sequence, TypeVar, overload

from .session import BaseBeaconSession
from .query import (
    JSONQuery,
    From,
    FromArrowDataset,
    FromBBFDataset,
    FromCSVDataset,
    FromNetCDFDataset,
    FromParquetDataset,
    FromZarrDataset,
)

SchemaType = dict[str, Any]
"""Alias describing the JSON payload returned by ``/api/dataset-schema``."""

DatasetFormatLiteral = Literal["arrow", "bbf", "csv", "netcdf", "parquet", "zarr"]
"""Literal union of dataset formats supported by the Beacon Node."""
_FormatT = TypeVar("_FormatT", bound=DatasetFormatLiteral)
FromFactory = Callable[[str, dict[str, Any]], From]

_DATASET_FROM_FACTORIES: Dict[str, FromFactory] = {
    "csv": lambda path, options: FromCSVDataset(paths=[path], delimiter=options.get("delimiter", ",")),
    "parquet": lambda path, _: FromParquetDataset(paths=[path]),
    "arrow": lambda path, _: FromArrowDataset(paths=[path]),
    "netcdf": lambda path, _: FromNetCDFDataset(paths=[path]),
    "zarr": lambda path, options: FromZarrDataset(paths=[path], statistics_columns=options.get("statistics_columns")),
    "bbf": lambda path, _: FromBBFDataset(paths=[path]),
}


class Dataset(Generic[_FormatT]):
    """File or object-store resource that Beacon can scan directly.

    The class acts as a light-weight descriptor containing the user's
    original ``file_path`` plus convenience methods to inspect schema
    information and kick off JSON query builders.
    """

    def __init__(self, http_session: BaseBeaconSession, file_path: str, file_format: _FormatT):
        """Create a dataset descriptor.

        Args:
            http_session: Session that knows how to communicate with the Beacon Node.
            file_path: Absolute/relative path or URI that Beacon can read.
            file_format: File format string supported by Beacon (e.g. ``parquet``).
        """

        self.session = http_session
        self.file_path = file_path
        self.file_format = file_format

    def get_file_path(self) -> str:
        """Return the original path/URI provided when constructing the dataset."""

        return self.file_path

    def get_file_format(self) -> str:
        """Return the declared file format string (case preserved)."""

        return self.file_format

    def get_file_name(self) -> str:
        """Return the basename portion of the dataset path/URI."""

        return os.path.basename(self.file_path.rstrip("/\\"))

    def get_schema(self) -> SchemaType:
        """Fetch the dataset schema by calling the Beacon Node.

        Returns:
            SchemaType: JSON-compatible schema description mirroring the
                server's ``/api/dataset-schema`` payload.

        Raises:
            RuntimeError: If the HTTP request fails.
            ValueError: When the response body is not valid JSON or the
                decoded value is not a JSON object.
            Exception: For unsupported field types surfaced by Beacon.
        """

        response = self.session.get("/api/dataset-schema", params={"file": self.file_path})
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get dataset schema: {response.text}")

        try:
            schema_data = response.json()
        except ValueError as exc:
            raise ValueError("Dataset schema response was not valid JSON") from exc

        if not isinstance(schema_data, dict):
            raise ValueError("Dataset schema response must be a JSON object")

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

    def get_file_extension(self) -> str:
        """Return the lowercase file extension without the leading dot."""

        file_name = self.get_file_name()
        _, extension = os.path.splitext(file_name)
        return extension.lstrip(".")

    def __str__(self) -> str:
        return self.file_path

    def __repr__(self) -> str:
        return f"Dataset(file_path={self.file_path})"

    @overload
    def query(self: "Dataset[Literal['csv']]", *, delimiter: str | None = None, **kwargs: Any) -> JSONQuery:
        ...

    @overload
    def query(self: "Dataset[Literal['zarr']]", *, statistics_columns: Sequence[str] | None = None, **kwargs: Any) -> JSONQuery:
        ...

    @overload
    def query(self, **kwargs: Any) -> JSONQuery:
        ...

    def query(
        self,
        *,
        delimiter: str | None = None,
        statistics_columns: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> JSONQuery:
        """Build a :class:`~beacon_api.query.JSONQuery` starting from this dataset.

        Args:
            delimiter: Optional CSV delimiter override (only valid for CSV datasets).
            statistics_columns: Optional Zarr statistics column names (only valid for Zarr datasets).
            **kwargs: Additional format-specific options forwarded to the query builder.

        Returns:
            JSONQuery: Query builder tied to this dataset source.

        Raises:
            ValueError: If a format-specific option is passed to the wrong
                dataset type or the format is not supported.
        """

        file_format_str = self.get_file_format().lower()
        builder = _DATASET_FROM_FACTORIES.get(file_format_str)

        if builder is None:
            supported = ", ".join(sorted(_DATASET_FROM_FACTORIES))
            raise ValueError(f"Unsupported dataset format '{file_format_str}'. Supported formats: {supported}")

        builder_options: dict[str, Any] = dict(kwargs)

        if delimiter is not None:
            if file_format_str != "csv":
                raise ValueError("The 'delimiter' option is only supported for CSV datasets.")
            builder_options["delimiter"] = delimiter

        if statistics_columns is not None:
            if file_format_str != "zarr":
                raise ValueError("The 'statistics_columns' option is only supported for Zarr datasets.")
            builder_options["statistics_columns"] = list(statistics_columns)

        _from = builder(self.file_path, builder_options)
        return JSONQuery(http_session=self.session, _from=_from)