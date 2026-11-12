import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.services.mission_service import MissionError, mission_service
from app.services.video_service import video_service
from app.services.vision_service import vision_service


@asynccontextmanager
async def lifespan(app):
    video_service.start()
    vision_service.start()
    if settings.MISSION_SCHEDULER_ENABLED:
        mission_service.start_scheduler()
    try:
        yield
    finally:
        await asyncio.to_thread(vision_service.stop)
        await asyncio.to_thread(video_service.stop)
        await asyncio.to_thread(mission_service.shutdown)


app = FastAPI(
    lifespan=lifespan, title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json", docs_url="/docs"
)

# Configuración de orígenes permitidos (frontend)
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectar rutas versión 1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"status": "ok", "message": "API Drones Autónomos activa"}


@app.exception_handler(MissionError)
async def mission_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})
