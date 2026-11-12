import os
from pathlib import Path
from uuid import uuid4


class EvidenceStore:
    def __init__(self, directory, max_bytes):
        self.directory = Path(directory)
        self.max_bytes = max_bytes

    def save(self, image, findings):
        import cv2

        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        annotated = image.copy()
        for finding in findings:
            x1, y1, x2, y2 = finding.box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(
                annotated,
                f"{finding.tipo} {finding.confidence:.2f}",
                (x1, max(15, y1)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
            )
        ok, jpeg = cv2.imencode(".jpg", annotated)
        if not ok:
            raise RuntimeError("No se pudo codificar evidencia")
        data = jpeg.tobytes()
        used = sum(path.stat().st_size for path in self.directory.glob("*.jpg"))
        if used + len(data) > self.max_bytes:
            raise RuntimeError("Cuota de evidencia agotada")
        filename = uuid4().hex + ".jpg"
        path = self.directory / filename
        # Nombre aleatorio exclusivo; solo se sirve después de registrar su URL en BD.
        with path.open("xb") as handle:
            os.chmod(path, 0o600)
            handle.write(data)
        return path
