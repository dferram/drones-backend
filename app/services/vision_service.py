import logging
import time
from collections import deque
from threading import Event, Lock, Thread

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.mission import Mision
from app.schemas.detection import DeteccionCreate
from app.services.drone_service import drone_service
from app.services.evidence_service import EvidenceStore
from app.services.ingestion_service import ingest_batch
from app.services.video_service import video_service

logger = logging.getLogger(__name__)


class VisionService:
    def __init__(self, config, video, drone, sessions, detector=None):
        self.config, self.video, self.drone, self.sessions = config, video, drone, sessions
        self.detector = detector
        self.store = EvidenceStore(config.EVIDENCE_DIR, config.EVIDENCE_MAX_BYTES)
        self.stop_event = Event()
        self.lock = Lock()
        self.worker = None
        self.state = "disabled"
        self.frames = self.detections = self.failures = 0
        self.latencies = deque(maxlen=1000)
        self.last_sequence = None

    def start(self):
        if not self.config.VISION_ENABLED or self.worker and self.worker.is_alive():
            return
        self.stop_event.clear()
        self.state = "starting"
        self.worker = Thread(target=self._run, name="vision-inference", daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=10)
        with self.lock:
            self.state = "stopping" if self.worker and self.worker.is_alive() else "stopped"

    def status(self):
        with self.lock:
            ordered = sorted(self.latencies)

            def percentile(p):
                return ordered[round((len(ordered) - 1) * p)] if ordered else None

            return {
                "state": self.state,
                "frames_processed": self.frames,
                "detections_saved": self.detections,
                "failures": self.failures,
                "latency_samples": len(ordered),
                "capture_to_db_p50_ms": percentile(0.5),
                "capture_to_db_p95_ms": percentile(0.95),
                "geolocation_source": self.config.VISION_GEO_SOURCE,
            }

    def process(self, frame):
        import cv2
        import numpy as np

        if time.monotonic() - frame.published_at > self.config.VIDEO_STALE_SECONDS:
            return 0
        if self.config.VISION_GEO_SOURCE == "simulated":
            lat, lon = self.config.VISION_LATITUDE, self.config.VISION_LONGITUDE
        else:
            telemetry = self.drone.telemetry()
            lat, lon = telemetry["latitude"], telemetry["longitude"]
        if lat is None or lon is None:
            raise RuntimeError("Sin coordenadas válidas para la detección")
        with self.sessions() as db:
            mission = db.query(Mision).filter(Mision.vehiculo_activo == 1).first()
            flight_id = mission.id if mission and self.config.VISION_GEO_SOURCE == "telemetry" else None
        image = cv2.imdecode(np.frombuffer(frame.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Frame JPEG inválido")
        findings = self.detector.detect(image)
        if not findings:
            with self.lock:
                self.frames += 1
            return 0
        path = self.store.save(image, findings)
        try:
            with self.sessions() as db:
                inputs = [
                    DeteccionCreate(
                        vuelo_id=flight_id,
                        tipo=f.tipo,
                        nivel_confianza=f.confidence,
                        frame_url=f"{self.config.API_V1_STR}/evidence/{path.name}",
                        latitud=lat,
                        longitud=lon,
                        timestamp=frame.captured_at,
                    )
                    for f in findings
                ]
                ingest_batch(db, inputs)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        with self.lock:
            self.frames += 1
            self.detections += len(findings)
            self.latencies.append((time.monotonic() - frame.published_at) * 1000 + frame.processing_ms)
        return len(findings)

    def _run(self):
        try:
            if self.detector is None:
                from app.vision.detector import DetectorGroup

                self.detector = DetectorGroup(self.config.VISION_MODELS, self.config.VISION_THRESHOLD)
            while not self.stop_event.is_set():
                frame = self.video.latest()
                if frame and frame.sequence != self.last_sequence:
                    self.last_sequence = frame.sequence
                    try:
                        self.process(frame)
                        with self.lock:
                            self.state = "running"
                    except Exception:
                        logger.exception("No se pudo procesar el frame de visión")
                        with self.lock:
                            self.state = "waiting_or_error"
                            self.failures += 1
                self.stop_event.wait(1 / self.config.VISION_FPS)
        except Exception:
            logger.exception("No se pudo inicializar el detector; revisar modelo y dependencias")
            with self.lock:
                self.state = "unavailable"
                self.failures += 1


vision_service = VisionService(settings, video_service, drone_service, SessionLocal)


def get_vision_service():
    return vision_service
