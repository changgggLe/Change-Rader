from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_intraday_anomalies_use_camel_case_contract() -> None:
    response = client.get("/api/v1/anomalies/intraday")
    payload = response.json()
    assert response.status_code == 200
    assert payload["marketStatus"] == "TRADING"
    assert payload["items"][0]["symbol"] == "603018"
    assert "lastPrice" in payload["items"][0]


def test_security_not_found() -> None:
    response = client.get("/api/v1/securities/000000")
    assert response.status_code == 404


def test_watchlist_add_and_remove() -> None:
    add_response = client.post("/api/v1/watchlist/603018")
    assert add_response.status_code == 201
    assert any(item["symbol"] == "603018" for item in add_response.json()["items"])

    remove_response = client.delete("/api/v1/watchlist/603018")
    assert remove_response.status_code == 204


def test_alert_setting() -> None:
    response = client.put("/api/v1/alerts/603018", json={"enabled": True})
    assert response.status_code == 200
    assert response.json() == {"symbol": "603018", "enabled": True}
