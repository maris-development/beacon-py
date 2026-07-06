"""Offline tests for query serialization (no Beacon node required).

These validate the JSON body produced by the builder without hitting the
network, so they run in any environment. They complement the integration tests
by pinning down the exact request shape the client sends to ``/api/query``.
"""

from __future__ import annotations

import json

from beacon_api.query import JSONQuery, SQLQuery
from beacon_api.query._from import FromTable


def _compile(query) -> dict:
    return json.loads(query.compile_query())


def test_sqlquery_compiles_to_sql_body():
    body = _compile(SQLQuery(http_session=None, query="SELECT 1"))
    assert body["sql"] == "SELECT 1"
    assert body["output"] is None


def test_jsonquery_select_and_from():
    q = JSONQuery(http_session=None, _from=FromTable("default"))
    q.add_select_column("Longitude", alias="lon").add_select_column("Latitude")
    body = _compile(q)

    assert body["from"] == "default"
    assert body["select"] == [
        {"column": "Longitude", "alias": "lon"},
        {"column": "Latitude", "alias": None},
    ]
    assert body["limit"] is None
    assert body["filters"] is None


def test_jsonquery_range_filter_body():
    q = JSONQuery(http_session=None, _from=FromTable("default"))
    q.add_select_column("Depth").add_range_filter("Depth", gt_eq=0, lt_eq=100)
    body = _compile(q)

    assert body["filters"] == [{"column": "Depth", "gt_eq": 0, "lt_eq": 100}]


def test_jsonquery_equals_and_null_filters():
    q = JSONQuery(http_session=None, _from=FromTable("default"))
    q.add_equals_filter("Cruise", "ABC").add_is_not_null_filter("Depth")
    body = _compile(q)

    assert {"column": "Cruise", "eq": "ABC"} in body["filters"]
    assert {"is_not_null": {"column": "Depth"}} in body["filters"]


def test_jsonquery_bbox_filter_body():
    q = JSONQuery(http_session=None, _from=FromTable("default"))
    q.add_bbox_filter("Longitude", "Latitude", bbox=(-10, 40, 10, 60))
    body = _compile(q)

    (bbox_filter,) = body["filters"]
    conditions = bbox_filter["and"]
    assert {"column": "Longitude", "gt_eq": -10, "lt_eq": None} in conditions
    assert {"column": "Longitude", "gt_eq": None, "lt_eq": 10} in conditions
    assert {"column": "Latitude", "gt_eq": 40, "lt_eq": None} in conditions
    assert {"column": "Latitude", "gt_eq": None, "lt_eq": 60} in conditions


def test_jsonquery_limit_offset_sort_distinct():
    q = JSONQuery(http_session=None, _from=FromTable("default"))
    q.add_select_column("Depth").add_sort("Depth", ascending=False)
    q.set_distinct(["Depth"]).set_limit(25).set_offset(5)
    body = _compile(q)

    assert body["limit"] == 25
    assert body["offset"] == 5
    assert body["sort_by"] == [{"Desc": "Depth"}]
    assert body["distinct"] == {"on": ["Depth"], "select": ["Depth"]}
