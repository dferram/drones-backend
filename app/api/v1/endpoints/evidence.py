import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.detection import Deteccion

router = APIRouter(dependencies=[Depends(deps.require_guard_or_admin)])


@router.get("/{filename}")
def read_evidence(filename: str, db: Session = Depends(deps.get_db)):
    if not re.fullmatch(r"[a-f0-9]{32}\.jpg", filename):
        raise HTTPException(404, "Evidencia no encontrada")
    url = f"{settings.API_V1_STR}/evidence/{filename}"
    if not db.query(Deteccion.id).filter(Deteccion.frame_url == url).first():
        raise HTTPException(404, "Evidencia no encontrada")
    root = Path(settings.EVIDENCE_DIR).resolve()
    path = root / filename
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, "Evidencia no encontrada")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    )
