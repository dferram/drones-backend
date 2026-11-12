import asyncio
import time
from dataclasses import replace

import cv2
import numpy as np
import pytest

from app.api.v1.endpoints.video import stream_frames
from app.core.config import Settings
from app.main import app
from app.services.video_service import VideoService, get_video_service


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise AssertionError("Tiempo agotado esperando video")


@pytest.fixture
def video():
    settings = Settings(
        _env_file=None, VIDEO_ENABLED=True, VIDEO_SOURCE="synthetic", VIDEO_WIDTH=320, VIDEO_HEIGHT=240, VIDEO_FPS=20
    )
    service = VideoService(settings)
    service.start()
    wait_for(service.latest)
    yield service
    service.stop()
    assert not service.worker.is_alive()


@pytest.fixture
def video_client(client, video):
    app.dependency_overrides[get_video_service] = lambda: video
    yield client
    app.dependency_overrides.pop(get_video_service, None)


def test_synthetic_frames_are_decodable_and_advance(video):
    first = video.latest()
    decoded = cv2.imdecode(np.frombuffer(first.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (240, 320, 3)
    next_frame = wait_for(lambda: video.latest() if video.latest().sequence > first.sequence else None)
    assert next_frame.jpeg != first.jpeg
    assert next_frame.processing_ms >= 0
    assert next_frame.captured_at.tzinfo is not None


def test_start_is_idempotent_and_stop_clears_frame(video):
    worker = video.worker
    video.start()
    assert video.worker is worker
    video.stop()
    assert video.latest() is None
    assert video.status()["state"] == "stopped"
    video.start()
    wait_for(video.latest)
    assert video.worker is not worker


def test_disabled_source_never_starts():
    service = VideoService(Settings(_env_file=None, VIDEO_ENABLED=False))
    service.start()
    assert service.worker is None
    assert service.latest() is None
    assert service.status()["state"] == "disabled"


@pytest.mark.parametrize("path", ["status", "frame", "stream"])
def test_video_requires_auth(client, path):
    assert client.get(f"/api/v1/video/{path}").status_code == 401


@pytest.mark.parametrize("role", ["admin_token", "guardia_token"])
def test_snapshot_permissions_and_headers(video_client, video, request, role):
    token = request.getfixturevalue(role)
    response = video_client.get("/api/v1/video/frame", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert int(response.headers["x-frame-sequence"]) > 0
    assert cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR) is not None


def test_missing_and_stale_frames_return_503(video_client, admin_token, video):
    headers = {"Authorization": f"Bearer {admin_token}"}
    video.stop()
    for path in ["frame", "stream"]:
        assert video_client.get(f"/api/v1/video/{path}", headers=headers).status_code == 503
    # Una última captura vieja no debe mostrarse como video en vivo.
    video.start()
    frame = wait_for(video.latest)
    video.stop()
    with video.lock:
        video.frame = replace(frame, published_at=video.clock() - 100)
        video.state = "running"
    assert video.latest() is None
    assert video.status()["state"] == "stale"
    assert video_client.get("/api/v1/video/frame", headers=headers).status_code == 503


def test_mjpeg_http_response(video_client, admin_token, video, monkeypatch):
    monkeypatch.setattr(video.settings, "VIDEO_STREAM_SECONDS", 0.25)
    response = video_client.get("/api/v1/video/stream", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
    chunks = response.content.split(b"--frame\r\n")[1:]
    assert len(chunks) >= 2
    for chunk in chunks:
        headers, payload = chunk.split(b"\r\n\r\n", 1)
        length = int(
            next(line.split(b": ")[1] for line in headers.split(b"\r\n") if line.startswith(b"Content-Length:"))
        )
        assert cv2.imdecode(np.frombuffer(payload[:length], dtype=np.uint8), cv2.IMREAD_COLOR) is not None
    assert response.content.endswith(b"--frame--\r\n")


@pytest.mark.asyncio
async def test_slow_subscriber_skips_old_frames_and_close_preserves_capture(video):
    stream = stream_frames(video, video.latest())
    first = await anext(stream)
    await asyncio.sleep(0.2)
    second = await anext(stream)

    def sequence(chunk):
        return int(chunk.split(b"X-Frame-Sequence: ")[1].split(b"\r\n")[0])

    assert sequence(second) > sequence(first) + 1
    await stream.aclose()
    assert video.worker.is_alive()


@pytest.mark.asyncio
async def test_stream_ends_when_source_disappears(video):
    stream = stream_frames(video, video.latest())
    await anext(stream)
    video.stop()
    assert await anext(stream) == b"--frame--\r\n"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


def test_local_file_replays_after_eof(tmp_path):
    path = str(tmp_path / "camera.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    assert writer.isOpened()
    for i in range(3):
        writer.write(np.full((240, 320, 3), i * 60, dtype=np.uint8))
    writer.release()
    service = VideoService(
        Settings(
            _env_file=None,
            VIDEO_ENABLED=True,
            VIDEO_SOURCE="file",
            VIDEO_FILE=path,
            VIDEO_FPS=30,
            VIDEO_RECONNECT_SECONDS=0.1,
        )
    )
    try:
        service.start()
        wait_for(lambda: service.status()["frames_published"] >= 6)
        assert service.status()["reconnections"] >= 1
    finally:
        service.stop()
    assert not service.worker.is_alive()


def test_missing_file_recovers_when_source_appears(tmp_path):
    path = str(tmp_path / "later.avi")
    service = VideoService(
        Settings(_env_file=None, VIDEO_ENABLED=True, VIDEO_SOURCE="file", VIDEO_FILE=path, VIDEO_RECONNECT_SECONDS=0.1)
    )
    try:
        service.start()
        wait_for(lambda: service.status()["reconnections"] >= 1)
        assert service.latest() is None
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
        assert writer.isOpened()
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
        writer.release()
        assert wait_for(service.latest).jpeg.startswith(b"\xff\xd8")
    finally:
        service.stop()


def test_status_reports_capture_metrics(video_client, admin_token):
    response = video_client.get("/api/v1/video/status", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["state"] == "running"
    assert data["frames_published"] > 0
    assert data["processing_ms"] >= 0
    assert data["frame_age_seconds"] >= 0


def test_missing_opencv_does_not_crash_api(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "cv2", None)
    service = VideoService(Settings(_env_file=None, VIDEO_ENABLED=True))
    try:
        service.start()
        wait_for(lambda: service.status()["state"] == "unavailable")
        assert service.latest() is None
    finally:
        service.stop()
