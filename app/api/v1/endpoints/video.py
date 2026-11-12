import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter()


class StreamInfoResponse(BaseModel):
    stream_url: str
    protocolo: str
    estado_camara: str
    resolucion: str
    fps: int


@router.get(
    "/stream-info",
    response_model=StreamInfoResponse,
    summary="Información del stream de video en vivo",
    description="Retorna la URL del servidor de streaming configurado para el dron (WebRTC/RTSP), su estado y resolución.",
)
def get_stream_info():
    return StreamInfoResponse(
        stream_url="ws://localhost:8554/live/drone-camera",
        protocolo="WebRTC",
        estado_camara="ONLINE",
        resolucion="1920x1080",
        fps=30,
    )


class VideoTelemetryManager:
    """Administra las conexiones que reciben telemetría sincronizada con el stream."""

    def __init__(self):
        self.active_subscribers: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_subscribers.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_subscribers:
            self.active_subscribers.remove(websocket)

    async def broadcast_telemetry(self, telemetry_data: dict):
        disconnected = []
        for connection in self.active_subscribers:
            try:
                await connection.send_json(telemetry_data)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


video_telemetry_manager = VideoTelemetryManager()


@router.websocket("/ws/telemetry")
async def websocket_video_telemetry(websocket: WebSocket):
    """
    Canal WebSocket para transmitir datos en vivo del dron sincronizados con el video:
    batería, altitud, coordenadas actuales y estado de grabación.
    """
    await video_telemetry_manager.connect(websocket)
    try:
        while True:
            # En un entorno real se lee de app.services.drone_service
            # Aquí se mantiene la escucha o se envían pings periódicos
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        video_telemetry_manager.disconnect(websocket)
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.api import deps
from app.services.video_service import VideoService, get_video_service

router = APIRouter()
protected = [Depends(deps.require_guard_or_admin)]
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


@router.get("/status", dependencies=protected)
def video_status(service: VideoService = Depends(get_video_service)):
    return service.status()


def available_frame(service):
    frame = service.latest()
    if frame is None:
        raise HTTPException(status_code=503, detail="No hay un frame de video reciente disponible")
    return frame


@router.get("/frame", dependencies=protected, responses={200: {"content": {"image/jpeg": {}}}})
def video_frame(service: VideoService = Depends(get_video_service)):
    frame = available_frame(service)
    return Response(
        frame.jpeg,
        media_type="image/jpeg",
        headers={
            **HEADERS,
            "X-Frame-Sequence": str(frame.sequence),
            "X-Captured-At": frame.captured_at.isoformat(),
        },
    )


async def stream_frames(service, first):
    deadline = time.monotonic() + service.settings.VIDEO_STREAM_SECONDS
    last_sequence = None
    frame = first
    try:
        while time.monotonic() < deadline:
            if frame is None:
                break  # Cerrar el stream; el cliente puede reconectar cuando vuelva la fuente.
            if frame.sequence != last_sequence:
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame.jpeg)}\r\n".encode()
                    + f"X-Frame-Sequence: {frame.sequence}\r\n".encode()
                    + f"X-Captured-At: {frame.captured_at.isoformat()}\r\n\r\n".encode()
                    + frame.jpeg
                    + b"\r\n"
                )
                last_sequence = frame.sequence
            await asyncio.sleep(1 / service.settings.VIDEO_FPS)
            frame = service.latest()
        yield b"--frame--\r\n"
    except asyncio.CancelledError:
        raise


@router.get("/stream", dependencies=protected)
def video_stream(service: VideoService = Depends(get_video_service)):
    first = available_frame(service)
    return StreamingResponse(
        stream_frames(service, first), media_type="multipart/x-mixed-replace; boundary=frame", headers=HEADERS
    )


@router.get("/viewer", include_in_schema=False)
def video_viewer():
    return FileResponse(
        Path(__file__).resolve().parents[3] / "static" / "monitor.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )
