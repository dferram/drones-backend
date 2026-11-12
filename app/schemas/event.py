from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.detection import DeteccionResponse


class EventoBase(BaseModel):
    tipo: str = Field(..., description="Tipo de evento: 'PERSONA_NOCTURNA' o 'HUMO_DETECTADO'")
    nivel_criticidad: str = Field(..., description="Criticidad: 'BAJA', 'MEDIA', 'ALTA' o 'CRITICA'")
    descripcion: str | None = None
    estado: str = Field(default="PENDIENTE", description="Estado: 'PENDIENTE', 'EN_REVISION' o 'RESUELTO'")


class EventoStatusUpdate(BaseModel):
    estado: str = Field(
        ...,
        pattern="^(EN_REVISION|RESUELTO)$",
        description="Nuevo estado del evento. Valores permitidos: 'EN_REVISION' o 'RESUELTO'",
        examples=["EN_REVISION"],
    )


class EventoResponse(EventoBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class EventoDetailResponse(EventoResponse):
    detecciones: list[DeteccionResponse] = []

    model_config = ConfigDict(from_attributes=True)
