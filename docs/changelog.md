# Changelog

All notable changes to this project will be documented in this file.

## [1.10.0] - 2025-12-07

### Breaking changes

- Raised the minimum supported Python version from 3.8 to 3.10 and promoted several previously-optional dependencies (`fsspec`, `dask`, `zarr`, `networkx`, `matplotlib`, `numpy`, `geopandas`) to core requirements. Lightweight environments may need to be recreated before upgrading.
- Reworked the query entry points to be table/dataset-first. `Client.list_tables()` now returns `DataTable` helpers, `Client.list_datasets()` mirrors that experience for raw files, and the legacy `Client.query()`/`Client.available_columns*()` helpers have been deprecated in favor of the richer table and dataset APIs.

### Added

- **Dataset-aware workflows.** `Client.list_datasets()` (Beacon ≥ 1.4.0) now surfaces every server-side dataset as a typed `Dataset` helper that can: fetch a `pyarrow.Schema`, expose metadata (`get_file_name()`, `get_file_format()`), and produce a JSON query builder via `.query()`. CSV and Zarr datasets accept format-specific options such as custom delimiters or statistics columns directly on the query call.
- **Beacon node management helpers.** Administrative operations—including `upload_dataset()`, `download_dataset()`, `delete_dataset()`, `create_logical_table()` and `delete_table()`—were added to `Client`. Each helper enforces `BaseBeaconSession.is_admin()` and server version gates so automation scripts can manage Beacon nodes safely.
- **Modular JSON query builder.** The monolithic `beacon_api.query` module has been replaced by a node-based package (e.g. `_from`, `select`, `filter`, `distinct`, `sort`, `functions`). This unlocks fluent helpers such as `add_select_column`, `add_select_coalesced`, `add_polygon_filter`, `set_distinct`, `add_sort`, and new function nodes (`Functions.concat`, `Functions.coalesce`, `Functions.try_cast_to_type`, `Functions.map_pressure_to_depth`, etc.) for assembling complex projections.
- **Geospatial and scientific outputs.** `BaseQuery` can now stream Arrow record batches (`execute_streaming`) and materialize results as GeoParquet, GeoPandas, NdNetCDF, NetCDF, Arrow, CSV, Parquet, Zarr, Ocean Data View exports, or directly into an xarray dataset. The helpers write responses chunk-by-chunk to disk to avoid loading full payloads into memory.
- **Documentation and site tooling.** The MkDocs configuration now ships topical guides under “Using the Data Lake” (Exploring, Querying, Tables, Datasets), API references powered by `mkdocstrings`, versioned docs via `mike`, and an example gallery (e.g. the World Ocean Database walkthrough) that mirrors the new SDK surface area.

### Changed

- `BaseBeaconSession` now detects the Beacon server version on construction, exposes `version_at_least()`, and checks admin capabilities with `is_admin()`. Higher-level helpers automatically guard experimental endpoints (datasets, logical tables, streaming outputs) behind these checks.
- `DataTable` introspection now fetches Arrow schemas through `/api/table-schema`, exposing precise field types for downstream tooling. The `subset()` helper applies the new dataclass-based filter nodes so you can reuse bounding-box, depth, and time filters elsewhere.
- Query materialization helpers such as `to_parquet`, `to_csv`, `to_arrow`, and `to_geoparquet` now stream response chunks to disk rather than buffering entire files in memory, improving stability on large exports.
- Documentation content was rewritten to align with the new APIs—`docs/getting_started.md`, `docs/using/*.md`, and the reference pages now showcase dataset-first queries, polygon filters, geospatial exports, and SQL parity.

### Fixed

- Eliminated runaway memory usage during large exports by switching every file writer to `response.iter_content()` streaming.
- Hardened dataset/table schema parsing: unsupported Beacon field types now trigger explicit exceptions, while timestamp formats are automatically mapped to the correct `pyarrow` timestamp resolution.

[1.10.0]: https://github.com/maris-development/beacon-py/compare/v1.0.8...release/1.1.0
