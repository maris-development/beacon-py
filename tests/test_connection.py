"""Connection, authentication and server-metadata integration tests."""

from __future__ import annotations

import pytest

from beacon_api import Client
from beacon_api.session import BaseBeaconSession

from .conftest import BEACON_URL, USER_AGENT, requires_server


@requires_server
def test_client_connects(client):
    """Constructing a Client against a live node succeeds."""
    assert client.session.base_url.rstrip("/") == BEACON_URL.rstrip("/")


@requires_server
def test_check_status_does_not_raise(client, capsys):
    """check_status() reaches /api/health and prints a version banner."""
    client.check_status()
    out = capsys.readouterr().out
    assert "Beacon Version" in out


@requires_server
def test_get_server_info(client):
    info = client.get_server_info()
    assert isinstance(info, dict)
    assert "beacon_version" in info
    # Version string looks like "1.8.0".
    assert info["beacon_version"].count(".") >= 1


@requires_server
def test_version_at_least(client):
    """The node is >= 1.0.0 but not absurdly high."""
    assert client.session.version_at_least(1, 0, 0) is True
    assert client.session.version_at_least(99, 0, 0) is False


# --- Offline validation (no server required) -------------------------------


def test_invalid_backend_raises():
    with pytest.raises(ValueError):
        BaseBeaconSession(BEACON_URL, backend="not-a-backend")


def test_basic_auth_must_be_pair():
    with pytest.raises(ValueError):
        Client(BEACON_URL, basic_auth=("only-user",), user_agent=USER_AGENT)  # type: ignore[arg-type]
