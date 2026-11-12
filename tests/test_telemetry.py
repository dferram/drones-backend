from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.telemetry import drone_service
from app.services import drone_service as module


@pytest.fixture
def vehicle(monkeypatch):
    vehicle = SimpleNamespace(
        last_heartbeat=0.4,
        armed=True,
        mode=SimpleNamespace(name="GUIDED"),
        location=SimpleNamespace(global_relative_frame=SimpleNamespace(lat=20.58, lon=-100.38, alt=15)),
        battery=SimpleNamespace(level=85),
        groundspeed=2.5,
    )
    monkeypatch.setattr(module, "_DRONEKIT_AVAILABLE", True)
    monkeypatch.setattr(drone_service, "vehicle", vehicle)
    return vehicle


@pytest.mark.parametrize("role", ["admin_token", "guardia_token"])
def test_authorized_telemetry(client, vehicle, role, request):
    token = request.getfixturevalue(role)
    response = client.get("/api/v1/telemetry/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["relative_altitude_m"] == 15
    assert data["latitude"] == 20.58
    assert data["longitude"] == -100.38
    assert data["battery_percent"] == 85
    assert data["mode"] == "GUIDED"
    assert data["armed"] is True
    assert data["timestamp"].endswith("Z")


def test_telemetry_requires_auth(client):
    assert client.get("/api/v1/telemetry/").status_code == 401


@pytest.mark.parametrize("heartbeat", [None, 6, float("nan"), float("inf"), -1])
def test_stale_telemetry_is_unavailable(client, admin_token, vehicle, heartbeat):
    vehicle.last_heartbeat = heartbeat
    response = client.get("/api/v1/telemetry/", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 503


def test_disconnected_telemetry(client, admin_token, monkeypatch):
    monkeypatch.setattr(drone_service, "vehicle", None)
    response = client.get("/api/v1/telemetry/", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 503


def test_missing_and_invalid_sensor_values(client, admin_token, vehicle):
    vehicle.location.global_relative_frame.lat = float("nan")
    vehicle.location.global_relative_frame.lon = 181
    vehicle.location.global_relative_frame.alt = None
    vehicle.battery.level = -1
    vehicle.groundspeed = float("inf")
    response = client.get("/api/v1/telemetry/", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    for field in ("latitude", "longitude", "relative_altitude_m", "battery_percent", "groundspeed_m_s"):
        assert response.json()[field] is None
