"""JSON query-builder integration tests (JSONQuery on the default table)."""

from __future__ import annotations

import pandas as pd
import pytest

from .conftest import requires_server

pytestmark = requires_server


def test_select_columns(default_table, select_columns):
    q = default_table.query()
    for col in select_columns:
        q.add_select_column(col)
    df = q.set_limit(5).to_pandas_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == select_columns
    assert len(df) <= 5


def test_select_alias(default_table, columns):
    df = (
        default_table.query()
        .add_select_column(columns["lon"], alias="longitude")
        .set_limit(3)
        .to_pandas_dataframe()
    )
    assert "longitude" in df.columns


def test_add_select_columns_bulk(default_table, columns):
    pairs = [(columns["lon"], "x"), (columns["lat"], "y")]
    df = default_table.query().add_select_columns(pairs).set_limit(3).to_pandas_dataframe()
    assert list(df.columns) == ["x", "y"]


def test_limit_bounds_rowcount(default_table, columns):
    df = default_table.query().add_select_column(columns["lon"]).set_limit(4).to_pandas_dataframe()
    assert len(df) <= 4


def test_range_filter(default_table, columns):
    col = columns["numeric"]
    if not col:
        pytest.skip("no numeric column available")
    df = (
        default_table.query()
        .add_select_column(col)
        .add_is_not_null_filter(col)
        .add_range_filter(col, gt_eq=0, lt_eq=100)
        .set_limit(50)
        .to_pandas_dataframe()
    )
    values = df[col].dropna()
    assert ((values >= 0) & (values <= 100)).all()


def test_is_not_null_filter(default_table, columns):
    col = columns["numeric"] or columns["string"]
    df = (
        default_table.query()
        .add_select_column(col)
        .add_is_not_null_filter(col)
        .set_limit(50)
        .to_pandas_dataframe()
    )
    assert df[col].notna().all()


def test_equals_filter(default_table, columns):
    col = columns["string"]
    if not col:
        pytest.skip("no string column available")
    sample = (
        default_table.query()
        .add_select_column(col)
        .add_is_not_null_filter(col)
        .set_limit(1)
        .to_pandas_dataframe()
    )
    if sample.empty:
        pytest.skip("table returned no rows for equality sampling")
    value = sample[col].iloc[0]
    df = (
        default_table.query()
        .add_select_column(col)
        .add_equals_filter(col, value)
        .set_limit(20)
        .to_pandas_dataframe()
    )
    assert (df[col] == value).all()


def test_bbox_filter(default_table, columns):
    lon, lat = columns["lon"], columns["lat"]
    if not (lon and lat):
        pytest.skip("no lon/lat columns available")
    df = (
        default_table.query()
        .add_select_column(lon)
        .add_select_column(lat)
        .add_bbox_filter(lon, lat, bbox=(-180, -90, 180, 90))
        .set_limit(50)
        .to_pandas_dataframe()
    )
    lons, lats = df[lon].dropna(), df[lat].dropna()
    assert ((lons >= -180) & (lons <= 180)).all()
    assert ((lats >= -90) & (lats <= 90)).all()


@pytest.mark.xfail(
    reason=(
        "Library bug: SortColumn.to_dict() emits the column name unquoted "
        "(e.g. {'Asc': 'Depth'}). The node parses sort_by as SQL and folds the "
        "unquoted identifier to lower case ('depth'), so sorting on any column "
        "whose name is not already lower case fails with a schema error. "
        "Quoting the identifier ({'Asc': '\"Depth\"'}) returns 200."
    ),
    strict=False,
)
def test_sort_ascending(default_table, columns):
    col = columns["numeric"]
    if not col:
        pytest.skip("no numeric column available")
    df = (
        default_table.query()
        .add_select_column(col)
        .add_is_not_null_filter(col)
        .add_sort(col, ascending=True)
        .set_limit(50)
        .to_pandas_dataframe()
    )
    values = df[col].dropna().tolist()
    assert values == sorted(values)


def test_distinct(default_table, columns):
    col = columns["string"]
    if not col:
        pytest.skip("no string column available")
    df = (
        default_table.query()
        .add_select_column(col)
        .set_distinct([col])
        .set_limit(50)
        .to_pandas_dataframe()
    )
    assert df[col].nunique(dropna=False) == len(df)


def test_offset_skips_rows(default_table, columns):
    # NOTE: intentionally avoids add_sort() — sorting on a mixed-case column is
    # currently broken server-side (see test_sort_ascending). The node returns
    # rows in a stable scan order across identical requests, which is enough to
    # verify that OFFSET shifts the window.
    col = columns["numeric"] or columns["lon"] or columns["string"]
    page0 = (
        default_table.query()
        .add_select_column(col)
        .set_limit(10)
        .to_pandas_dataframe()
    )
    page1 = (
        default_table.query()
        .add_select_column(col)
        .set_limit(10)
        .set_offset(10)
        .to_pandas_dataframe()
    )
    if len(page0) < 10 or page1.empty:
        pytest.skip("not enough rows to verify offset")
    # Offsetting past the first page must yield a different window.
    assert not page0.reset_index(drop=True).equals(page1.reset_index(drop=True))


def test_explain_returns_plan(default_table, columns):
    plan = (
        default_table.query()
        .add_select_column(columns["lon"] or columns["string"])
        .set_limit(1)
        .explain()
    )
    # The node returns a list of plan nodes (each a dict with a "Plan" key).
    assert isinstance(plan, (list, dict))
    assert plan  # non-empty plan
    if isinstance(plan, list):
        assert all(isinstance(node, dict) for node in plan)


def test_subset_helper(default_table, columns):
    lon, lat, ts, depth = columns["lon"], columns["lat"], columns["timestamp"], columns["numeric"]
    if not (lon and lat and ts and depth):
        pytest.skip("subset() needs lon/lat/time/depth columns")
    q = default_table.subset(
        longitude_column=lon,
        latitude_column=lat,
        time_column=ts,
        depth_column=depth,
        columns=[columns["string"]] if columns["string"] else [],
        bbox=(-180, -90, 180, 90),
    )
    df = q.set_limit(20).to_pandas_dataframe()
    assert lon in df.columns and lat in df.columns
