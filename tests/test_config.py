import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("secret", ["", "short"])
def test_rejects_short_secret(secret):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=secret)


def test_requires_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "values",
    [
        {"EVENT_TIMEZONE": "invalid/zone"},
        {"EVENT_DEDUP_SECONDS": 0},
        {"EVENT_DEDUP_RADIUS_M": -1},
        {"EVENT_DEDUP_RADIUS_M": float("inf")},
    ],
)
def test_rejects_invalid_event_settings(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "values",
    [
        {"VIDEO_SOURCE": "rtsp"},
        {"VIDEO_FPS": 0},
        {"VIDEO_FPS": 31},
        {"VIDEO_WIDTH": 10000},
        {"VIDEO_HEIGHT": 0},
        {"VIDEO_STREAM_SECONDS": 0},
        {"VIDEO_STALE_SECONDS": float("inf")},
        {"VIDEO_JPEG_QUALITY": 101},
    ],
)
def test_rejects_invalid_video_settings(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
