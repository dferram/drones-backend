from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.detections import ingest_detection
from app.core.config import settings
from app.db.base_class import Base
from app.models.detection import Deteccion
from app.models.event import Evento
from app.schemas.detection import DeteccionCreate

PAYLOAD = {
    "tipo": "HUMO",
    "nivel_confianza": 0.9,
    "latitud": 20.5888,
    "longitud": -100.3899,
    "timestamp": "2026-10-19T23:00:00-06:00",
    "frame_url": "/storage/frame.jpg",
}


@pytest.fixture(autouse=True)
def rule_settings(monkeypatch):
    monkeypatch.setattr(settings, "EVENT_TIMEZONE", "America/Mexico_City")
    monkeypatch.setattr(settings, "EVENT_DEDUP_SECONDS", 60)
    monkeypatch.setattr(settings, "EVENT_DEDUP_RADIUS_M", 30)


@pytest.fixture
def ingest(client, admin_token):
    def send(**changes):
        return client.post(
            "/api/v1/detections/ingest",
            json=PAYLOAD | changes,
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    return send


def test_ingest_requires_auth(client, db):
    assert client.post("/api/v1/detections/ingest", json=PAYLOAD).status_code == 401
    assert db.query(Deteccion).count() == 0


def test_guard_cannot_ingest(client, guardia_token, db):
    response = client.post(
        "/api/v1/detections/ingest", json=PAYLOAD, headers={"Authorization": f"Bearer {guardia_token}"}
    )
    assert response.status_code == 403
    assert db.query(Deteccion).count() == 0


@pytest.mark.parametrize(
    "change",
    [
        {"tipo": "AUTO"},
        {"nivel_confianza": 1.1},
        {"latitud": 91},
        {"longitud": -181},
        {"timestamp": "2026-10-19T23:00:00"},
        {"vuelo_id": 0},
        {"frame_url": "a" * 256},
        {"unexpected": True},
    ],
)
def test_invalid_input(ingest, db, change):
    assert ingest(**change).status_code == 422
    assert db.query(Deteccion).count() == 0


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("2026-10-20T03:00:00Z", True),  # 21:00 local, límite incluido
        ("2026-10-20T11:59:59Z", True),
        ("2026-10-20T12:00:00Z", False),  # 06:00 local, límite excluido
        ("2026-10-20T02:59:59Z", False),
        ("2026-10-19T23:00:00-06:00", True),
    ],
)
def test_person_rule_uses_local_timezone(ingest, timestamp, expected):
    response = ingest(tipo=" persona ", timestamp=timestamp)
    assert response.status_code == 201
    assert response.json()["tipo"] == "PERSONA"
    assert (response.json()["evento_id"] is not None) is expected
    assert response.json()["timestamp"].endswith("Z")


@pytest.mark.parametrize("confidence,expected", [(0.69, False), (0.70, True)])
def test_confidence_threshold(ingest, confidence, expected):
    response = ingest(nivel_confianza=confidence)
    assert response.status_code == 201
    assert (response.json()["evento_id"] is not None) is expected


def test_duplicate_frames_share_event_and_preserve_evidence(ingest, client, guardia_token, db):
    first = ingest().json()
    second = ingest(timestamp="2026-10-20T05:00:30Z", frame_url="/storage/second.jpg").json()
    assert first["id"] != second["id"]
    assert first["evento_id"] == second["evento_id"]
    assert db.query(Evento).count() == 1
    headers = {"Authorization": f"Bearer {guardia_token}"}
    detail = client.get(f"/api/v1/events/{first['evento_id']}", headers=headers)
    assert detail.status_code == 200
    assert {d["frame_url"] for d in detail.json()["detecciones"]} == {"/storage/frame.jpg", "/storage/second.jpg"}
    response = client.patch(
        f"/api/v1/events/{first['evento_id']}/status", json={"estado": "EN_REVISION"}, headers=headers
    )
    assert response.status_code == 200
    assert ingest().json()["evento_id"] == first["evento_id"]
    filtered = client.get(
        "/api/v1/events/",
        params={"tipo": "HUMO_DETECTADO", "fecha_inicio": "2026-10-20T00:00:00", "fecha_fin": "2026-10-21T00:00:00"},
        headers=headers,
    )
    assert [event["id"] for event in filtered.json()] == [first["evento_id"]]


@pytest.mark.parametrize(
    "change",
    [
        {"timestamp": "2026-10-20T05:01:01Z"},
        {"latitud": 20.60},
        {"vuelo_id": 5},
        {"tipo": "PERSONA"},
    ],
)
def test_distinct_incidents_do_not_merge(ingest, change):
    first = ingest().json()
    second = ingest(**change).json()
    assert first["evento_id"] != second["evento_id"]


def test_fixed_window_does_not_extend_with_frames(ingest):
    first = ingest().json()
    assert ingest(timestamp="2026-10-20T05:01:00Z").json()["evento_id"] == first["evento_id"]
    assert ingest(timestamp="2026-10-20T05:01:30Z").json()["evento_id"] != first["evento_id"]


def test_out_of_order_frames(ingest):
    first = ingest().json()
    assert ingest(timestamp="2026-10-20T04:59:30Z").json()["evento_id"] == first["evento_id"]


def test_resolved_event_does_not_capture_new_detection(ingest, client, guardia_token):
    first = ingest().json()
    response = client.patch(
        f"/api/v1/events/{first['evento_id']}/status",
        json={"estado": "RESUELTO"},
        headers={"Authorization": f"Bearer {guardia_token}"},
    )
    assert response.status_code == 200
    assert ingest().json()["evento_id"] != first["evento_id"]


def test_default_time_is_utc(ingest, db):
    response = ingest(timestamp=None)
    assert response.status_code == 201
    assert response.json()["timestamp"].endswith("Z")
    assert db.query(Deteccion).one().timestamp.tzinfo is None


def test_failure_rolls_back_detection(ingest, db, monkeypatch):
    def fail(*args):
        raise RuntimeError("Rule failure")

    monkeypatch.setattr("app.services.ingestion_service.evaluate_detection_for_event", fail)
    with pytest.raises(RuntimeError, match="Rule failure"):
        ingest()
    assert db.query(Deteccion).count() == 0
    assert db.query(Evento).count() == 0


def test_concurrent_ingestion_uses_one_event(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def send(_):
        with sessions() as db:
            return ingest_detection(DeteccionCreate(**PAYLOAD), db).evento_id

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            ids = list(executor.map(send, range(8)))
        assert len(set(ids)) == 1
        with sessions() as db:
            assert db.query(Deteccion).count() == 8
            assert db.query(Evento).count() == 1
    finally:
        engine.dispose()


def test_event_date_filters_normalize_offset(ingest, client, guardia_token):
    event_id = ingest().json()["evento_id"]
    response = client.get(
        "/api/v1/events/",
        params={
            "fecha_inicio": "2026-10-19T22:59:59-06:00",
            "fecha_fin": "2026-10-19T23:00:01-06:00",
        },
        headers={"Authorization": f"Bearer {guardia_token}"},
    )
    assert response.status_code == 200
    assert [event["id"] for event in response.json()] == [event_id]
    assert response.json()[0]["created_at"] == "2026-10-20T05:00:00Z"


def test_event_date_filters_reject_reversed_interval(client, guardia_token):
    response = client.get(
        "/api/v1/events/",
        params={
            "fecha_inicio": "2026-10-21T00:00:00Z",
            "fecha_fin": "2026-10-20T00:00:00Z",
        },
        headers={"Authorization": f"Bearer {guardia_token}"},
    )
    assert response.status_code == 422
