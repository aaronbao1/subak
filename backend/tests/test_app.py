from pathlib import Path

import pytest

from app.config import DEFAULT_DB_PATH, Settings, SettingsError


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:3000", "http://localhost"])
def test_cors_allows_localhost_origin(client, origin):
    r = client.options(
        "/api/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in r.headers


@pytest.mark.parametrize("origin", ["https://evil.example.com", "http://localhost.evil.com", "http://10.0.0.5:3000"])
def test_cors_rejects_non_local_origin(client, origin):
    r = client.get("/api/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in r.headers


def test_settings_read_env(tmp_path: Path):
    s = Settings.from_env(
        {
            "BACKEND_DB_PATH": str(tmp_path / "x.db"),
            "BACKEND_PORT": "9001",
            "FORECAST_PROVIDER": "unavailable",
            "DROID_RUNNER": "sdk",
            "BACKEND_ALLOW_RESET": "1",
        }
    )
    assert s.db_path == tmp_path / "x.db"
    assert s.port == 9001
    assert s.forecast_provider == "unavailable"
    assert s.droid_runner == "sdk"
    assert s.allow_reset is True


def test_settings_defaults():
    s = Settings.from_env({})
    assert s.port == 8787
    assert s.db_path == DEFAULT_DB_PATH
    assert s.forecast_provider == "placeholder"
    assert s.droid_runner == "fake"
    assert s.allow_reset is False


@pytest.mark.parametrize(
    "env",
    [
        {"BACKEND_PORT": "abc"},
        {"BACKEND_PORT": "70000"},
        {"DROID_RUNNER": "real"},
        {"FORECAST_PROVIDER": "prophet"},
    ],
)
def test_settings_reject_bad_values(env):
    with pytest.raises(SettingsError):
        Settings.from_env(env)


def test_unknown_route_uses_error_envelope(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert set(body["error"]) == {"code", "message", "details"}


def test_db_file_created_at_configured_path(app, db_path):
    assert db_path.exists()
