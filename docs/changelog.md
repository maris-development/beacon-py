# Changelog

All notable changes to this project will be documented in this file.

## [1.3.3] - 2026-07-10

### Added

- Support for the newer Arrow type spellings that `pyarrow.type_for_alias` does not accept, including the "view" and "large" variants: `Utf8View`/`StringView`, `BinaryView`, `LargeUtf8`, `LargeBinary`, and `Boolean`. The view types are resolved defensively, so the package stays importable on older `pyarrow` builds that do not provide them.

### Changed

- An unrecognised column type no longer aborts schema discovery. `DataTable.get_schema()` and `Dataset.get_schema()` now fall back to a `null`-typed field and emit a `RuntimeWarning` for that column instead of raising, so one unknown type no longer makes the whole table or dataset unreadable. Code that relied on the previous exception should check for `pyarrow.null()` fields or promote the warning with `warnings.simplefilter("error", RuntimeWarning)`.
- `Dataset.get_schema()` now shares the table schema parsing instead of duplicating its own timestamp branches, so both paths accept exactly the same set of types.

## [1.3.2] - 2026-07-07

### Changed

- `DataTable` now initialises against `/api/table-schema` on Beacon ≥ 1.7.0, falling back to `/api/table-config` on older nodes. On 1.7.0+ the config endpoint no longer supplies table metadata, so `get_table_type()` and `get_table_description()` return `None` there; both remain populated against earlier servers.

## [1.3.1] - 2026-06-11

### Added

- `Client(..., user_agent="my-app/1.0 (you@example.com)")` sets a `User-Agent` header on every request. Recommended on shared or public nodes so traffic can be attributed to your application.
- `Client.sql_query_streaming()` runs raw SQL immediately and returns a `pyarrow.RecordBatchStreamReader` (Beacon ≥ 1.5.0), so result sets too large to buffer can be consumed batch by batch. Unlike `sql_query()`, it does not return a builder.

### Changed

- Timestamp type parsing accepts more spellings: the abbreviated `Timestamp(ns)` form in addition to `Timestamp(Millisecond, None)`, an optional timezone clause, short unit aliases (`s`, `ms`, `us`, `ns`), and case-insensitive matching. Timezone names keep their original case.
- README and the documentation site were revised to cover the streaming helpers, dataset workflows, and the new `user_agent` option.

## [1.3.0] - 2026-06-03

### Fixed

- Arrow schema parsing was reworked to handle the string form Beacon emits since the 1.2.0 schema change — `"Timestamp(Millisecond, None)"` — alongside the original dict form `{"Timestamp": ["Millisecond", None]}`. Timezone-aware timestamps such as `Timestamp(Second, Some("UTC"))` are now mapped to a `pyarrow` timestamp carrying that timezone; previously any string-typed timestamp was passed to `pyarrow` unchanged and timezone-aware ones raised an "Unsupported data type" exception.

## [1.2.1] - 2026-01-21

### Fixed

- `Distinct.to_dict()` wrapped its payload in a redundant `distinct` key, producing a doubly-nested JSON query body that the Beacon Node rejected. The node now emits `on` and `select` at the top level, so `set_distinct()` queries are accepted.

## [1.2.0] - 2026-01-14

### Breaking changes

- Query streaming now returns a `pyarrow.RecordBatchStreamReader` from `Query.execute_streaming()` instead of yielding individual `RecordBatch` objects. This allows users to manage the stream lifecycle directly and integrate with Arrow's native reading/writing utilities.

## [1.1.3] - 2025-12-09

### Added

- `JSONQuery.set_limit()` and `JSONQuery.set_offset()` for paging through large result sets; both are emitted as `limit`/`offset` in the JSON query body.
- `BaseBeaconSession` accepts `proxy_headers` at construction, so custom headers can be supplied when building a session directly rather than through `Client`.

### Fixed

- `SortColumn` emitted lower-cased `asc`/`desc` keys, which the Beacon Node did not recognise. It now emits `Asc`/`Desc`, so `add_sort()` actually orders results.

## [1.1.2] - 2025-12-08

### Added

- Type stubs (`.pyi`) for the public API, so editors and type checkers can surface signatures for `Client`, `DataTable`, `Dataset`, the query nodes, and the session helpers.

## [1.1.1] - 2025-12-08

Re-release of 1.1.0 with no source changes.

## [1.1.0] - 2025-12-07

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

[1.3.3]: https://github.com/maris-development/beacon-py/compare/1.3.2...1.3.3
[1.3.2]: https://github.com/maris-development/beacon-py/compare/1.3.1...1.3.2
[1.3.1]: https://github.com/maris-development/beacon-py/compare/1.3.0...1.3.1
[1.3.0]: https://github.com/maris-development/beacon-py/compare/v1.2.1...1.3.0
[1.2.1]: https://github.com/maris-development/beacon-py/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/maris-development/beacon-py/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/maris-development/beacon-py/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/maris-development/beacon-py/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/maris-development/beacon-py/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/maris-development/beacon-py/compare/v1.0.8...v1.1.0
