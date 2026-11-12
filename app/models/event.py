from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.detection import Deteccion

if TYPE_CHECKING:
    from app.models.detection import Deteccion


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)  # PERSONA_NOCTURNA, HUMO_DETECTADO
    nivel_criticidad: Mapped[str] = mapped_column(String(20), default="ALTA")  # BAJA, MEDIA, ALTA, CRITICA
    descripcion: Mapped[str] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="PENDIENTE")  # PENDIENTE, EN_REVISION, RESUELTO
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Se referencia con string "Deteccion"
    detecciones: Mapped[list["Deteccion"]] = relationship("Deteccion", back_populates="evento")
