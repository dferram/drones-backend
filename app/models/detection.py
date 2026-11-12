from asyncio import Event
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.event import Evento


class Deteccion(Base):
    __tablename__ = "detecciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vuelo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)  # "PERSONA" o "HUMO"
    nivel_confianza: Mapped[float] = mapped_column(Float, nullable=False)
    frame_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitud: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    longitud: Mapped[float] = mapped_column(Numeric(11, 8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Clave foránea hacia la tabla 'eventos'
    evento_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("eventos.id"), nullable=True)

    # Se referencia con string "Evento" sin necesidad de importar la clase
    evento: Mapped["Event"] = relationship("Evento", back_populates="detecciones")
    evento: Mapped["Evento"] = relationship("Evento", back_populates="detecciones")
