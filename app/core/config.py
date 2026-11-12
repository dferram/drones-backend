from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.vision import ModelSpec


class Settings(BaseSettings):
    PROJECT_NAME: str = "Drones-Autonomos API"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql://drone_user:drone_password@localhost:5432/drone_db"
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    MISSION_SCHEDULER_ENABLED: bool = False
    EVENT_TIMEZONE: str = "America/Mexico_City"
    EVENT_DEDUP_SECONDS: int = Field(60, ge=1, le=3600)
    EVENT_DEDUP_RADIUS_M: float = Field(30, gt=0, le=1000, allow_inf_nan=False)
    VIDEO_ENABLED: bool = False
    VIDEO_SOURCE: Literal["synthetic", "file"] = "synthetic"
    VIDEO_FILE: str = ""
    VIDEO_WIDTH: int = Field(640, ge=160, le=1920)
    VIDEO_HEIGHT: int = Field(360, ge=120, le=1080)
    VIDEO_FPS: int = Field(10, ge=1, le=30)
    VIDEO_JPEG_QUALITY: int = Field(80, ge=30, le=95)
    VIDEO_STALE_SECONDS: float = Field(3, ge=1, le=30, allow_inf_nan=False)
    VIDEO_RECONNECT_SECONDS: float = Field(1, ge=0.1, le=30, allow_inf_nan=False)
    VIDEO_STREAM_SECONDS: int = Field(60, ge=1, le=300)
    VISION_ENABLED: bool = False
    VISION_MODELS: list[ModelSpec] = Field(default_factory=list)
    VISION_THRESHOLD: float = Field(0.7, gt=0, le=1, allow_inf_nan=False)
    VISION_FPS: int = Field(2, ge=1, le=10)
    VISION_GEO_SOURCE: Literal["telemetry", "simulated"] = "telemetry"
    VISION_LATITUDE: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    VISION_LONGITUDE: float | None = Field(None, ge=-180, le=180, allow_inf_nan=False)
    EVIDENCE_DIR: str = "data/evidence"
    EVIDENCE_MAX_BYTES: int = Field(1024 * 1024 * 1024, ge=1024)

    @field_validator("EVENT_TIMEZONE")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Zona horaria IANA desconocida") from exc
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()