"""Una fuente y un buffer de último frame por proceso; sin cola por espectador."""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoFrame:
    sequence: int
    captured_at: datetime
    published_at: float
    jpeg: bytes
    processing_ms: float


class VideoService:
    def __init__(self, settings, *, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.lock = Lock()
        self.stop_event = Event()
        self.worker = None
        self.frame = None
        self.sequence = 0
        self.reconnections = 0
        self.state = "disabled"

    def start(self):
        with self.lock:
            if not self.settings.VIDEO_ENABLED or (self.worker and self.worker.is_alive()):
                return
            self.stop_event.clear()
            self.frame = None
            self.state = "starting"
            self.worker = Thread(target=self._run, name="video-capture", daemon=True)
            self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=5)
        with self.lock:
            self.frame = None
            self.state = "stopping" if self.worker and self.worker.is_alive() else "stopped"

    def latest(self):
        with self.lock:
            frame = self.frame
            if self.state != "running" or frame is None:
                return None
            if self.clock() - frame.published_at > self.settings.VIDEO_STALE_SECONDS:
                return None
            return frame

    def status(self):
        with self.lock:
            frame = self.frame
            age = max(0, self.clock() - frame.published_at) if frame else None
            return {
                "enabled": self.settings.VIDEO_ENABLED,
                "source": self.settings.VIDEO_SOURCE,
                "state": "stale" if self.state == "running" and age > self.settings.VIDEO_STALE_SECONDS else self.state,
                "frames_published": self.sequence,
                "reconnections": self.reconnections,
                "frame_age_seconds": age,
                "processing_ms": frame.processing_ms if frame else None,
                "captured_at": frame.captured_at if frame else None,
            }

    def _run(self):
        capture = None
        try:
            import cv2
            import numpy as np

            while not self.stop_event.is_set():
                started = self.clock()
                try:
                    if self.settings.VIDEO_SOURCE == "synthetic":
                        frame = np.zeros((self.settings.VIDEO_HEIGHT, self.settings.VIDEO_WIDTH, 3), dtype=np.uint8)
                        x = (self.sequence * 8) % max(1, self.settings.VIDEO_WIDTH - 50)
                        cv2.rectangle(frame, (x, 50), (x + 40, 100), (0, 200, 255), -1)
                        cv2.putText(
                            frame,
                            f"SIMULATED {self.sequence + 1}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 255, 255),
                            1,
                        )
                    else:
                        if capture is None:
                            path = Path(self.settings.VIDEO_FILE)
                            if not path.is_file():
                                raise RuntimeError("Archivo de video no disponible")
                            capture = cv2.VideoCapture(str(path.resolve()))
                        ok, frame = capture.read()
                        if not ok:
                            raise RuntimeError("Fin de archivo o lectura de video fallida")
                    captured_at = datetime.now(UTC)
                    frame = cv2.resize(frame, (self.settings.VIDEO_WIDTH, self.settings.VIDEO_HEIGHT))
                    ok, encoded = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.settings.VIDEO_JPEG_QUALITY]
                    )
                    if not ok:
                        raise RuntimeError("No se pudo codificar el frame")
                    now = self.clock()
                    with self.lock:
                        self.sequence += 1
                        self.frame = VideoFrame(
                            self.sequence, captured_at, now, encoded.tobytes(), (now - started) * 1000
                        )
                        self.state = "running"
                    self.stop_event.wait(max(0, 1 / self.settings.VIDEO_FPS - (self.clock() - started)))
                except Exception:
                    logger.warning("Fuente de video no disponible; se reintentará", exc_info=True)
                    if capture is not None:
                        capture.release()
                        capture = None
                    with self.lock:
                        self.frame = None
                        self.state = "reconnecting"
                        self.reconnections += 1
                    self.stop_event.wait(self.settings.VIDEO_RECONNECT_SECONDS)
        except ImportError:
            logger.exception("Instala las dependencias de video para activar la captura")
            with self.lock:
                self.state = "unavailable"
        finally:
            if capture is not None:
                capture.release()


video_service = VideoService(settings)


def get_video_service():
    return video_service
