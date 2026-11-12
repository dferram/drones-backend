from fastapi import APIRouter, Depends, HTTPException

from app.api import deps
from app.schemas.telemetry import TelemetryResponse
from app.services.drone_service import drone_service

router = APIRouter()


@router.get("/", response_model=TelemetryResponse, dependencies=[Depends(deps.require_guard_or_admin)])
def get_telemetry():
    """Consulta el vehículo conectado; no inicia conexiones ni comandos de vuelo."""
    try:
        return drone_service.telemetry()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
