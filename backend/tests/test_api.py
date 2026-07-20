from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings.config import Settings


def make_settings(database_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{database_path.as_posix()}",
        cache_backend="memory",
        auto_create_tables=True,
        seed_demo_data=True,
        internal_user_key="test-user",
        market_data_provider="database_demo",
    )


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    app = create_app(make_settings(tmp_path / "api.db"))
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "ok"
    assert response.json()["cache"] == "ok"
    assert response.json()["market_sync"] == "idle"


def test_intraday_anomalies_use_database_and_camel_case_contract(client: TestClient) -> None:
    response = client.get("/api/v1/anomalies/intraday")
    payload = response.json()
    assert response.status_code == 200
    assert payload["marketStatus"] == "TRADING"
    assert payload["items"][0]["symbol"] == "603018"
    assert "lastPrice" in payload["items"][0]
    assert client.get("/api/v1/market/status").json()["source"] == "DATABASE_DEMO"


def test_security_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/securities/000000")
    assert response.status_code == 404


def test_watchlist_mutation_invalidates_cached_ranking(client: TestClient) -> None:
    first_ranking = client.get("/api/v1/anomalies/intraday").json()
    first_item = next(item for item in first_ranking["items"] if item["symbol"] == "603018")
    assert first_item["watched"] is False

    add_response = client.post("/api/v1/watchlist/603018")
    assert add_response.status_code == 201

    refreshed_ranking = client.get("/api/v1/anomalies/intraday").json()
    refreshed_item = next(item for item in refreshed_ranking["items"] if item["symbol"] == "603018")
    assert refreshed_item["watched"] is True

    remove_response = client.delete("/api/v1/watchlist/603018")
    assert remove_response.status_code == 204


def test_alert_setting(client: TestClient) -> None:
    response = client.put("/api/v1/alerts/603018", json={"enabled": True})
    assert response.status_code == 200
    assert response.json() == {"symbol": "603018", "enabled": True}
    assert client.get("/api/v1/securities/603018").json()["alerted"] is True


def test_watchlist_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "persistent.db"
    settings = make_settings(database_path)

    with TestClient(create_app(settings)) as first_client:
        assert first_client.post("/api/v1/watchlist/603018").status_code == 201

    with TestClient(create_app(settings)) as second_client:
        symbols = [item["symbol"] for item in second_client.get("/api/v1/watchlist").json()["items"]]
        assert "603018" in symbols


def test_watchlists_are_isolated_by_user_header(client: TestClient) -> None:
    user_a = {"X-User-Key": "device_user_a"}
    user_b = {"X-User-Key": "device_user_b"}

    assert client.post("/api/v1/watchlist/603018", headers=user_a).status_code == 201
    symbols_a = [item["symbol"] for item in client.get("/api/v1/watchlist", headers=user_a).json()["items"]]
    symbols_b = [item["symbol"] for item in client.get("/api/v1/watchlist", headers=user_b).json()["items"]]

    assert "603018" in symbols_a
    assert "603018" not in symbols_b


def test_wechat_openid_takes_precedence_over_device_user_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "wechat-identity.db")
    settings.wechat_appid = "wx-test-appid"
    headers = {
        "X-User-Key": "device_user_a",
        "X-WX-OPENID": "openid_user_a",
        "X-WX-APPID": "wx-test-appid",
    }

    with TestClient(create_app(settings)) as test_client:
        assert test_client.post("/api/v1/watchlist/603018", headers=headers).status_code == 201
        openid_symbols = [
            item["symbol"] for item in test_client.get("/api/v1/watchlist", headers=headers).json()["items"]
        ]
        device_symbols = [
            item["symbol"]
            for item in test_client.get("/api/v1/watchlist", headers={"X-User-Key": "device_user_a"}).json()["items"]
        ]

    assert "603018" in openid_symbols
    assert "603018" not in device_symbols


def test_rejects_unexpected_wechat_appid(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "wechat-appid.db")
    settings.wechat_appid = "wx-expected-appid"

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get(
            "/api/v1/watchlist",
            headers={"X-WX-OPENID": "openid_user_a", "X-WX-APPID": "wx-other-appid"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "微信小程序身份不匹配"


def test_can_require_cloudbase_wechat_identity(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "wechat-required.db")
    settings.require_wechat_identity = True

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/api/v1/watchlist")

    assert response.status_code == 401
    assert response.json()["detail"] == "缺少微信用户身份"
