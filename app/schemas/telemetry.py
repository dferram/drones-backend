from datetime import datetime

from pydantic import BaseModel


class TelemetryResponse(BaseModel):
    timestamp: datetime
    heartbeat_age_seconds: float
    armed: bool
    mode: str | None
    latitude: float | None
    longitude: float | None
    relative_altitude_m: float | None
    battery_percent: float | None
    groundspeed_m_s: float | None
