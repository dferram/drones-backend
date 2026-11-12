from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, field_validator


class DeteccionBase(BaseModel):
    vuelo_id: int | None = Field(None, description="ID del vuelo en curso si existe")
    tipo: str = Field(..., description="Tipo de detección: 'PERSONA' o 'HUMO'")
    nivel_confianza: float = Field(..., ge=0.0, le=1.0, examples=[0.89])
    frame_url: str | None = Field(None, description="URL/path del frame con bounding box")
    latitud: float = Field(..., ge=-90.0, le=90.0, examples=[20.5888])
    longitud: float = Field(..., ge=-180.0, le=180.0, examples=[-100.3899])
    timestamp: datetime | None = None


class DeteccionCreate(DeteccionBase):
  """Payload de ingesta: el id y evento_id los genera el backend."""
  pass
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    tipo: Literal["PERSONA", "HUMO"]
    vuelo_id: int | None = Field(None, gt=0)
    frame_url: str | None = Field(None, min_length=1, max_length=255)
    timestamp: AwareDatetime | None = None

    @field_validator("tipo", mode="before")
    @classmethod
    def normalize_type(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class DeteccionResponse(DeteccionBase):
    id: int
    timestamp: datetime
    evento_id: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
