from datetime import UTC, datetime
from threading import RLock

from sqlalchemy import text

from app.models.detection import Deteccion
from app.services.event_rules import evaluate_detection_for_event

_ingest_lock = RLock()


def ingest_batch(db, inputs):
    """Una transacción para todas las detecciones de un frame y sus eventos."""
    with _ingest_lock:
        try:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(76240127)"))
            detections = []
            for item in inputs:
                timestamp = item.timestamp or datetime.now(UTC)
                detection = Deteccion(
                    **item.model_dump(exclude={"timestamp"}), timestamp=timestamp.astimezone(UTC).replace(tzinfo=None)
                )
                db.add(detection)
                db.flush()
                evaluate_detection_for_event(db, detection)
                detections.append(detection)
            db.commit()
            return detections
        except Exception:
            db.rollback()
            raise
