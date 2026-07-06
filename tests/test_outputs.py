"""Output/export integration tests: files written by the query helpers."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq
import pytest

from .conftest import requires_server

pytestmark = requires_server


@pytest.fixture(scope="session")
def backend():
    """Pin exports to a single backend.

    Overrides the parametrized ``backend`` fixture from conftest: output/export
    formats are produced by ``/api/query`` identically regardless of the
    discovery backend, so running these slow file-writing tests once (REST) is
    enough. Backend-specific behaviour is covered in ``test_backends.py``.
    """
    return "rest"


@pytest.fixture
def small_query(default_table, select_columns):
    """A bounded query (<= 20 rows) used by every export test."""

    def _build():
        q = default_table.query()
        for col in select_columns:
            q.add_select_column(col)
        return q.set_limit(20)

    return _build


def test_to_parquet(small_query, select_columns, tmp_path):
    path = tmp_path / "out.parquet"
    small_query().to_parquet(str(path))
    assert path.exists() and path.stat().st_size > 0
    table = pq.read_table(path)
    assert set(select_columns).issubset(set(table.column_names))


def test_to_csv(small_query, tmp_path):
    path = tmp_path / "out.csv"
    small_query().to_csv(str(path))
    assert path.exists() and path.stat().st_size > 0
    df = pd.read_csv(path)
    assert len(df) <= 20


def test_to_arrow_file(small_query, tmp_path):
    import pyarrow as pa
    import pyarrow.ipc as ipc

    path = tmp_path / "out.arrow"
    small_query().to_arrow(str(path))
    assert path.exists() and path.stat().st_size > 0
    # to_arrow() writes the Arrow *file* (random-access) format, not a stream.
    with pa.memory_map(str(path), "r") as source:
        table = ipc.open_file(source).read_all()
    assert table.num_rows <= 20


GEOPARQUET_XFAIL = pytest.mark.xfail(
    reason=(
        "The geoparquet output format crashes the Beacon node: every request "
        "closes the connection (RemoteDisconnected) instead of returning data. "
        "Reproduced deterministically against Beacon 1.8.0."
    ),
    strict=False,
    raises=Exception,
)


@GEOPARQUET_XFAIL
def test_to_geoparquet(default_table, columns, tmp_path):
    lon, lat = columns["lon"], columns["lat"]
    if not (lon and lat):
        pytest.skip("no lon/lat columns available")
    path = tmp_path / "out.geoparquet"
    default_table.query().add_select_column(lon).add_select_column(lat).set_limit(20).to_geoparquet(
        str(path), longitude_column=lon, latitude_column=lat
    )
    assert path.exists() and path.stat().st_size > 0


@GEOPARQUET_XFAIL
def test_to_geo_pandas_dataframe(default_table, columns):
    lon, lat = columns["lon"], columns["lat"]
    if not (lon and lat):
        pytest.skip("no lon/lat columns available")
    gdf = (
        default_table.query()
        .add_select_column(lon)
        .add_select_column(lat)
        .set_limit(20)
        .to_geo_pandas_dataframe(lon, lat)
    )
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert "geometry" in gdf.columns


def test_to_netcdf(small_query, tmp_path):
    path = tmp_path / "out.nc"
    small_query().to_netcdf(str(path))
    assert path.exists() and path.stat().st_size > 0


def test_to_zarr(small_query, tmp_path):
    path = tmp_path / "out.zarr"
    small_query().to_zarr(str(path))
    assert path.exists()
