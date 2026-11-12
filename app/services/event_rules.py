"""Reglas de eventos; las fechas persistidas se interpretan como UTC."""

import math
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.alert import Alerta
from app.core.config import settings
from app.models.detection import Deteccion
from app.models.event import Evento
from app.services.notfication_service import notification_manager

UMBRAL_CONFIANZA = 0.70


async def evaluate_detection_for_event(
    db: Session, deteccion: Deteccion
) -> Evento | None:
    """
    Evalúa la detección. Si cumple las condiciones de seguridad, genera el Evento,
    crea la Alerta vinculada y emite la notificación en tiempo real vía WebSocket.
    """
    if deteccion.nivel_confianza < UMBRAL_CONFIANZA:
        return None

    tipo_normalizado = deteccion.tipo.upper()
    fecha_eval = deteccion.timestamp or datetime.utcnow()
    hora = fecha_eval.hour

    nuevo_evento = None
    titulo_alerta = ""
    mensaje_alerta = ""
    criticidad = "ALTA"

    # 1. Regla de Humo
    if tipo_normalizado == "HUMO":
        criticidad = "CRITICA"
        titulo_alerta = "ALERTA CRÍTICA: Humo Detectado"
        mensaje_alerta = (
            f"Se detectó humo con {(deteccion.nivel_confianza * 100):.1f}% de confianza "
            f"en coordenadas [{deteccion.latitud}, {deteccion.longitud}]."
        )
        nuevo_evento = Evento(
            tipo="HUMO_DETECTADO",
            nivel_criticidad=criticidad,
            descripcion=mensaje_alerta,
            estado="PENDIENTE",
            created_at=fecha_eval,
        )

    # 2. Regla de Persona fuera de horario (21:00 a 06:00 hrs)
    elif tipo_normalizado == "PERSONA":
        es_fuera_de_horario = hora >= 21 or hora < 6
        if es_fuera_de_horario:
            criticidad = "ALTA"
            titulo_alerta = "ALERTA DE SEGURIDAD: Persona Fuera de Horario"
            mensaje_alerta = (
                f"Presencia de persona detectada a las {fecha_eval.strftime('%H:%M:%S')} hrs "
                f"con confianza del {(deteccion.nivel_confianza * 100):.1f}%."
            )
            nuevo_evento = Evento(
                tipo="PERSONA_NOCTURNA",
                nivel_criticidad=criticidad,
                descripcion=mensaje_alerta,
                estado="PENDIENTE",
                created_at=fecha_eval,
            )

    # Si califica como evento, persistimos evento, asociamos detección y disparamos alerta
    if nuevo_evento:
        db.add(nuevo_evento)
        db.flush()

        deteccion.evento_id = nuevo_evento.id
        db.add(deteccion)

        # Crear y persistir la Alerta
        nueva_alerta = Alerta(
            evento_id=nuevo_evento.id,
            titulo=titulo_alerta,
            mensaje=mensaje_alerta,
            nivel_criticidad=criticidad,
            leida=False,
            destinatario_rol="GUARDIA",
            timestamp_envio=fecha_eval,
        )
        db.add(nueva_alerta)
        db.flush()

        # Emitir broadcast en tiempo real vía WebSocket
        payload_broadcast = {
            "type": "NEW_ALERT",
            "alerta_id": nueva_alerta.id,
            "evento_id": nuevo_evento.id,
            "titulo": nueva_alerta.titulo,
            "mensaje": nueva_alerta.mensaje,
            "nivel_criticidad": nueva_alerta.nivel_criticidad,
            "timestamp": nueva_alerta.timestamp_envio.isoformat(),
            "evidencia": {
                "frame_url": deteccion.frame_url,
                "latitud": float(deteccion.latitud),
                "longitud": float(deteccion.longitud),
            },
        }
        await notification_manager.broadcast_alert(payload_broadcast)

    return nuevo_evento
def distance_m(lat1, lon1, lat2, lon2):
    lat1, lat2 = math.radians(float(lat1)), math.radians(float(lat2))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, a))))


def evaluate_detection_for_event(db: Session, deteccion: Deteccion) -> Evento | None:
    """Agrupa evidencia cercana de un vuelo en un evento abierto de ventana fija."""
    if deteccion.nivel_confianza < UMBRAL_CONFIANZA:
        return None
    fecha = deteccion.timestamp
    local = fecha.replace(tzinfo=UTC).astimezone(ZoneInfo(settings.EVENT_TIMEZONE))
    if deteccion.tipo == "HUMO":
        tipo, criticidad = "HUMO_DETECTADO", "CRITICA"
    elif deteccion.tipo == "PERSONA" and (local.hour >= 21 or local.hour < 6):
        tipo, criticidad = "PERSONA_NOCTURNA", "ALTA"
    else:
        return None

    window = timedelta(seconds=settings.EVENT_DEDUP_SECONDS)
    candidates = (
        db.query(Evento)
        .filter(
            Evento.tipo == tipo,
            Evento.estado.in_(["PENDIENTE", "EN_REVISION"]),
            Evento.created_at >= fecha - window,
            Evento.created_at <= fecha + window,
        )
        .order_by(Evento.created_at.desc(), Evento.id.desc())
        .all()
    )
    for event in candidates:
        # Comparar con la primera evidencia evita extender la región con cada frame.
        anchor = db.query(Deteccion).filter(Deteccion.evento_id == event.id).order_by(Deteccion.id).first()
        if anchor is not None and anchor.vuelo_id == deteccion.vuelo_id:
            if (
                distance_m(anchor.latitud, anchor.longitud, deteccion.latitud, deteccion.longitud)
                <= settings.EVENT_DEDUP_RADIUS_M
            ):
                deteccion.evento_id = event.id
                return event

    event = Evento(
        tipo=tipo,
        nivel_criticidad=criticidad,
        descripcion=(
            f"{deteccion.tipo} con confianza del {deteccion.nivel_confianza * 100:.1f}% "
            f"en ({deteccion.latitud}, {deteccion.longitud}); hora local {local.isoformat()}."
        ),
        estado="PENDIENTE",
        created_at=fecha,
    )
    db.add(event)
    db.flush()
    deteccion.evento_id = event.id
    return event
