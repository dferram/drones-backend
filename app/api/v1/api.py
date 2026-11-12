from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.detections import router as detections_router
from app.api.v1.endpoints.event import router as events_router
from app.api.v1.endpoints.missions import router as missions_router
from app.api.v1.endpoints import (
    alerts,
    auth,
    detections,
    event,
    missions,
    video,
    drone
)

from app.api.v1.endpoints import alerts, auth, detections, drone, event, evidence, missions, telemetry, video, vision

api_router = APIRouter()


@api_router.get("/")
def v1_root():
  return {
      "version": "v1",
      "description": "API REST - Drones Autónomos 67",
      "endpoints_disponibles": [
          "/api/v1/auth/login",
          "/api/v1/auth/register",
          "/api/v1/auth/me",
          "/api/v1/missions/",
          "/api/v1/drone/",
          "/api/v1/detections/ingest",
      ],
  }
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(missions.router, prefix="/missions", tags=["Misiones"])
api_router.include_router(
    detections.router, prefix="/detections", tags=["Detecciones"]
)
api_router.include_router(event.router, prefix="/events", tags=["Eventos"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alertas"])
api_router.include_router(video.router, prefix="/video", tags=["Video"])
    return {
        "version": "v1",
        "description": "API REST - Drones Autónomos 67",
        "endpoints_disponibles": [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/me",
            "/api/v1/missions/",
            "/api/v1/drone/",
            "/api/v1/telemetry/",
            "/api/v1/detections/ingest",
            "/api/v1/events/",
            "/api/v1/video/status",
            "/api/v1/video/stream",
        ],
    }

api_router.include_router(drone.router, prefix="/drone", tags=["Control de Vuelo"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["Telemetría"])
api_router.include_router(detections.router, prefix="/detections", tags=["Detecciones"])
api_router.include_router(event.router, prefix="/events", tags=["Eventos"])
api_router.include_router(video.router, prefix="/video", tags=["Video"])

api_router.include_router(evidence.router, prefix="/evidence", tags=["Evidencia"])
api_router.include_router(vision.router, prefix="/vision", tags=["Visión"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alertas"])
