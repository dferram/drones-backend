"""Prueba real ONNX -> evidencia -> BD -> alerta API en SQLite temporal y ubicación simulada."""

import argparse
import json
import os
import secrets
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path("models/person-model.json"))
    parser.add_argument("--image", type=Path, default=Path("data/person-demo.jpg"))
    parser.add_argument("--output", type=Path, default=Path("docs/validation/vision-report.json"))
    args = parser.parse_args()
    os.environ.update(
        SECRET_KEY=secrets.token_hex(32),
        DATABASE_URL="sqlite:///:memory:",
        MISSION_SCHEDULER_ENABLED="false",
        VIDEO_ENABLED="false",
        VISION_ENABLED="false",
    )
    import cv2
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api import deps
    from app.core.config import Settings, settings
    from app.core.security import create_access_token, get_password_hash
    from app.main import app
    from app.models import Base
    from app.models.user import Rol, Usuario
    from app.schemas.vision import ModelSpec
    from app.services.video_service import VideoFrame
    from app.services.vision_service import VisionService
    from app.vision.detector import DetectorGroup

    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError("Imagen no disponible")
    ok, jpeg = cv2.imencode(".jpg", image)
    assert ok
    specs = [ModelSpec.model_validate(item) for item in json.loads(args.models.read_text())]
    detector = DetectorGroup(specs)
    with tempfile.TemporaryDirectory(prefix="vision-acceptance-") as folder:
        folder = Path(folder)
        engine = create_engine(f"sqlite:///{folder / 'test.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        config = Settings(
            _env_file=None,
            VISION_GEO_SOURCE="simulated",
            VISION_LATITUDE=20.58,
            VISION_LONGITUDE=-100.38,
            EVIDENCE_DIR=str(folder / "evidence"),
        )
        service = VisionService(config, None, None, sessions, detector)
        original_dir = settings.EVIDENCE_DIR
        settings.EVIDENCE_DIR = config.EVIDENCE_DIR

        def get_db():
            with sessions() as db:
                yield db

        app.dependency_overrides[deps.get_db] = get_db
        try:
            with sessions.begin() as db:
                role = Rol(nombre="GUARDIA")
                db.add(role)
                db.flush()
                user = Usuario(
                    nombre="Vision test",
                    email="vision@example.com",
                    rol_id=role.id,
                    password_hash=get_password_hash("Test-vision-123!"),
                    activo=True,
                )
                db.add(user)
                db.flush()
                token = create_access_token(subject=user.id)
            for index in range(5):
                frame = VideoFrame(index, datetime(2026, 10, 20, 5, tzinfo=UTC), time.monotonic(), jpeg.tobytes(), 0)
                assert service.process(frame) > 0
            with TestClient(app) as client:
                headers = {"Authorization": f"Bearer {token}"}
                alerts = client.get("/api/v1/alerts/", headers=headers)
                assert alerts.status_code == 200
                events = alerts.json()
                assert len(events) == 1
                assert events[0]["tipo"] == "PERSONA_NOCTURNA"
                evidence = client.get(events[0]["detecciones"][0]["frame_url"], headers=headers)
                assert evidence.status_code == 200
                ack = client.post(f"/api/v1/alerts/{events[0]['id']}/ack", headers=headers)
                assert ack.status_code == 200
            report = {
                "passed": True,
                "fixture": str(args.image),
                "simulated_geolocation_and_nighttime": True,
                "events": len(events),
                "detections": len(events[0]["detecciones"]),
                "evidence_read_http_status": evidence.status_code,
                "ack_state": ack.json()["estado"],
                "metrics": service.status(),
                "limitation": "Public test image; not an independent precision/recall evaluation or flight video",
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
        finally:
            settings.EVIDENCE_DIR = original_dir
            app.dependency_overrides.clear()
            engine.dispose()


if __name__ == "__main__":
    main()
