from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.models.event import Evento
from app.models.user import Usuario
from app.schemas.event import (
    EventoDetailResponse,
    EventoResponse,
    EventoStatusUpdate,
)

router = APIRouter()


@router.get(
    "/",
    response_model=list[EventoResponse],
    summary="Listar eventos de seguridad",
    description=("Lista eventos con filtros de tipo, estado, fechas y paginación. Accesible por Guardia y Admin."),
)
def list_events(
    tipo: str | None = Query(None, description="Filtrar por tipo (ej. PERSONA_NOCTURNA, HUMO_DETECTADO)"),
    estado: str | None = Query(None, description="Filtrar por estado (ej. PENDIENTE, EN_REVISION, RESUELTO)"),
    fecha_inicio: datetime | None = Query(None, description="Fecha/hora inicial de búsqueda (ISO 8601)"),
    fecha_fin: datetime | None = Query(None, description="Fecha/hora final de búsqueda (ISO 8601)"),
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(50, ge=1, le=100, description="Cantidad máxima de registros a retornar"),
    db: Session = Depends(deps.get_db),
    current_user: Usuario = Depends(deps.require_guard_or_admin),
):
    query = db.query(Evento)

    # La BD guarda UTC sin tzinfo; los filtros sin offset también se interpretan como UTC.
    if fecha_inicio and fecha_inicio.tzinfo:
        fecha_inicio = fecha_inicio.astimezone(UTC).replace(tzinfo=None)
    if fecha_fin and fecha_fin.tzinfo:
        fecha_fin = fecha_fin.astimezone(UTC).replace(tzinfo=None)
    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
        raise HTTPException(status_code=422, detail="fecha_inicio debe ser anterior o igual a fecha_fin")

    if tipo:
        query = query.filter(Evento.tipo == tipo.upper())
    if estado:
        query = query.filter(Evento.estado == estado.upper())
    if fecha_inicio:
        query = query.filter(Evento.created_at >= fecha_inicio)
    if fecha_fin:
        query = query.filter(Evento.created_at <= fecha_fin)

    eventos = query.order_by(Evento.created_at.desc()).offset(skip).limit(limit).all()
    return eventos


@router.get(
    "/{id}",
    response_model=EventoDetailResponse,
    summary="Obtener detalle de un evento",
    description="Retorna un evento con sus detecciones y enlaces a los frames de evidencia visual.",
)
def get_event(
    id: int,
    db: Session = Depends(deps.get_db),
    current_user: Usuario = Depends(deps.require_guard_or_admin),
):
    evento = db.query(Evento).options(joinedload(Evento.detecciones)).filter(Evento.id == id).first()
    if not evento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado",
        )
    return evento


@router.patch(
    "/{id}/status",
    response_model=EventoResponse,
    summary="Actualizar estado del evento",
    description="Permite que el guardia o administrador actualice el estado del incidente a EN_REVISION o RESUELTO.",
)
def update_event_status(
    id: int,
    status_in: EventoStatusUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Usuario = Depends(deps.require_guard_or_admin),
):
    evento = db.query(Evento).filter(Evento.id == id).first()
    if not evento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado",
        )

    evento.estado = status_in.estado
    db.commit()
    db.refresh(evento)
    return evento
