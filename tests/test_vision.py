import time
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from app.core.config import Settings, settings
from app.models.detection import Deteccion
from app.models.event import Evento
from app.schemas.vision import ModelSpec
from app.services.video_service import VideoFrame
from app.services.vision_service import VisionService
from app.vision.detector import Finding, OnnxDetector
from app.vision.evaluate import evaluate
from tests.conftest import TestingSessionLocal


@pytest.fixture
def frame():
    ok, encoded = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))
    assert ok
    return VideoFrame(1, datetime(2026, 10, 20, 5, tzinfo=UTC), time.monotonic(), encoded.tobytes(), 2)


@pytest.fixture
def vision(tmp_path, db, monkeypatch):
    monkeypatch.setattr(settings, "EVIDENCE_DIR", str(tmp_path))
    config = Settings(
        _env_file=None,
        VISION_ENABLED=True,
        VISION_GEO_SOURCE="simulated",
        VISION_LATITUDE=20.58,
        VISION_LONGITUDE=-100.38,
        EVIDENCE_DIR=str(tmp_path),
    )
    detector = Mock()
    detector.detect.return_value = [Finding("HUMO", 0.95, (10, 20, 80, 90))]
    return VisionService(config, Mock(), Mock(), TestingSessionLocal, detector)


def test_frame_to_alert_evidence_and_ack(vision, frame, client, guardia_token, db):
    assert vision.process(frame) == 1
    assert db.query(Deteccion).count() == 1
    headers = {"Authorization": f"Bearer {guardia_token}"}
    response = client.get("/api/v1/alerts/", headers=headers)
    assert response.status_code == 200
    event = response.json()[0]
    assert event["tipo"] == "HUMO_DETECTADO"
    evidence = client.get(event["detecciones"][0]["frame_url"], headers=headers)
    assert evidence.status_code == 200
    assert cv2.imdecode(np.frombuffer(evidence.content, dtype=np.uint8), cv2.IMREAD_COLOR) is not None
    assert client.get(event["detecciones"][0]["frame_url"]).status_code == 401
    for _ in range(2):
        ack = client.post(f"/api/v1/alerts/{event['id']}/ack", headers=headers)
        assert ack.status_code == 200
        assert ack.json()["estado"] == "EN_REVISION"
    assert client.get("/api/v1/alerts/", params={"after_id": event["id"]}, headers=headers).json() == []
    assert vision.status()["capture_to_db_p95_ms"] >= 0


def test_no_findings_writes_no_evidence(vision, frame, db, tmp_path):
    vision.detector.detect.return_value = []
    assert vision.process(frame) == 0
    assert list(tmp_path.iterdir()) == []
    assert db.query(Deteccion).count() == 0


def test_multiple_findings_share_one_evidence(vision, frame, db, tmp_path):
    vision.detector.detect.return_value += [Finding("PERSONA", 0.9, (100, 20, 140, 160))]
    assert vision.process(frame) == 2
    assert len(list(tmp_path.glob("*.jpg"))) == 1
    assert db.query(Evento).count() == 2
    assert len({d.frame_url for d in db.query(Deteccion)}) == 1


def test_persistence_failure_removes_orphan_evidence(vision, frame, db, tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr("app.services.ingestion_service.evaluate_detection_for_event", fail)
    with pytest.raises(RuntimeError):
        vision.process(frame)
    assert list(tmp_path.glob("*.jpg")) == []
    assert db.query(Deteccion).count() == 0


def test_full_storage_blocks_persistence(vision, frame, db):
    vision.store.max_bytes = 1
    with pytest.raises(RuntimeError, match="Cuota"):
        vision.process(frame)
    assert db.query(Deteccion).count() == 0


def test_telemetry_loss_does_not_fabricate_coordinates(vision, frame, db):
    vision.config.VISION_GEO_SOURCE = "telemetry"
    vision.drone.telemetry.side_effect = RuntimeError("Disconnected")
    with pytest.raises(RuntimeError):
        vision.process(frame)
    vision.detector.detect.assert_not_called()
    assert db.query(Deteccion).count() == 0


def test_stale_frame_is_skipped(vision, frame):
    assert vision.process(replace(frame, published_at=time.monotonic() - 100)) == 0
    vision.detector.detect.assert_not_called()


def test_orphan_and_invalid_evidence_not_served(client, guardia_token, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EVIDENCE_DIR", str(tmp_path))
    filename = "a" * 32 + ".jpg"
    (tmp_path / filename).write_bytes(b"orphan")
    headers = {"Authorization": f"Bearer {guardia_token}"}
    assert client.get(f"/api/v1/evidence/{filename}", headers=headers).status_code == 404
    assert client.get("/api/v1/evidence/secret.env", headers=headers).status_code == 404


def detector_for_decode():
    detector = OnnxDetector.__new__(OnnxDetector)
    detector.spec = ModelSpec(path="test.onnx", labels={0: "PERSONA", 1: "HUMO"}, class_count=2)
    detector.threshold, detector.nms_threshold = 0.7, 0.45
    return detector


def test_onnx_decode_nms_and_class_mapping():
    detector = detector_for_decode()
    output = np.array(
        [
            [
                [100, 100, 50, 80, 0.9, 0.1],
                [101, 100, 50, 80, 0.8, 0.1],
                [100, 100, 50, 80, 0.1, 0.95],
                [20, 20, 10, 10, 0.1, 0.2],
            ]
        ],
        dtype=np.float32,
    ).transpose(0, 2, 1)
    result = detector.decode(output, (320, 240), 1, 0, 0)
    assert len(result) == 2  # NMS elimina solo el duplicado de la misma clase.
    assert {item.tipo for item in result} == {"PERSONA", "HUMO"}
    assert result[0].box == (75, 60, 125, 140)


def test_letterbox_scaling_and_invalid_outputs():
    detector = detector_for_decode()
    output = np.array([[[320, 320, 200, 200, 0.9, 0.1]]], dtype=np.float32).transpose(0, 2, 1)
    assert detector.decode(output, (320, 160), 2, 0, 160)[0].box == (110, 30, 210, 130)
    with pytest.raises(ValueError, match="incompatible"):
        detector.decode(np.zeros((1, 10, 6)), (320, 160), 2, 0, 160)
    output[0, 0, 0] = np.nan
    assert detector.decode(output, (320, 160), 2, 0, 160) == []


def test_evaluation_counts_false_positives_and_missed_objects(tmp_path):
    cv2.imwrite(str(tmp_path / "sample.jpg"), np.zeros((200, 200, 3), dtype=np.uint8))
    detector = SimpleNamespace(
        detect=lambda _: [Finding("PERSONA", 0.9, (10, 10, 50, 100)), Finding("HUMO", 0.8, (100, 100, 150, 150))]
    )
    records = [
        {
            "image": "sample.jpg",
            "annotations": [
                {"tipo": "PERSONA", "box": [10, 10, 50, 100]},
                {"tipo": "PERSONA", "box": [60, 10, 90, 100]},
            ],
        }
    ]
    report = evaluate(detector, records, tmp_path)
    assert report["classes"]["PERSONA"] == {"tp": 1, "fp": 0, "fn": 1, "precision": 1, "recall": 0.5}
    assert report["classes"]["HUMO"]["fp"] == 1
    assert report["classes"]["HUMO"]["recall"] is None


def test_missing_models_reports_unavailable(vision):
    vision.detector = None
    vision.start()
    vision.worker.join(timeout=5)
    assert vision.status()["state"] == "unavailable"
    vision.stop()
