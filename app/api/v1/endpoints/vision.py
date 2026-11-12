from fastapi import APIRouter, Depends

from app.api import deps
from app.services.vision_service import VisionService, get_vision_service

router = APIRouter(dependencies=[Depends(deps.require_guard_or_admin)])


@router.get("/status")
def vision_status(service: VisionService = Depends(get_vision_service)):
    return service.status()
