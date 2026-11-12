"""Adaptador YOLOv8 ONNX sin NMS: RGB /255, letterbox 114, salida [1,4+C,N]."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.schemas.vision import ModelSpec as ModelSpec


@dataclass(frozen=True)
class Finding:
    tipo: str
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 en la imagen original


class OnnxDetector:
    def __init__(self, spec, threshold=0.7, nms_threshold=0.45):
        if not Path(spec.path).is_file():
            raise ValueError("No existe el modelo ONNX configurado")
        if any(key < 0 or key >= spec.class_count for key in spec.labels):
            raise ValueError("Índice de clase fuera de rango")
        self.spec, self.threshold, self.nms_threshold = spec, threshold, nms_threshold
        self.net = cv2.dnn.readNetFromONNX(spec.path)

    def detect(self, image):
        height, width = image.shape[:2]
        size = self.spec.input_size
        scale = min(size / width, size / height)
        resized = cv2.resize(image, (round(width * scale), round(height * scale)))
        left, top = (size - resized.shape[1]) // 2, (size - resized.shape[0]) // 2
        canvas = np.full((size, size, 3), 114, dtype=np.uint8)
        canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
        self.net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255, (size, size), swapRB=True, crop=False))
        return self.decode(self.net.forward(), (width, height), scale, left, top)

    def decode(self, output, dimensions, scale, left, top):
        expected = 4 + self.spec.class_count
        if output.ndim != 3 or output.shape[0] != 1 or output.shape[1] != expected:
            raise ValueError("Salida ONNX incompatible; se requiere [1,4+clases,N], sin objectness ni NMS")
        width, height = dimensions
        grouped = {}
        for row in output[0].T:
            if not np.isfinite(row).all():
                continue
            class_id = int(np.argmax(row[4:]))
            confidence = float(row[4 + class_id])
            if class_id not in self.spec.labels or not self.threshold <= confidence <= 1:
                continue
            cx, cy, w, h = row[:4]
            if w <= 0 or h <= 0:
                continue
            x1 = max(0, min(width, round((float(cx - w / 2) - left) / scale)))
            y1 = max(0, min(height, round((float(cy - h / 2) - top) / scale)))
            x2 = max(0, min(width, round((float(cx + w / 2) - left) / scale)))
            y2 = max(0, min(height, round((float(cy + h / 2) - top) / scale)))
            if x2 <= x1 or y2 <= y1:
                continue
            tipo = self.spec.labels[class_id]
            grouped.setdefault(tipo, []).append(Finding(tipo, confidence, (x1, y1, x2, y2)))
        findings = []
        for candidates in grouped.values():
            boxes = [[f.box[0], f.box[1], f.box[2] - f.box[0], f.box[3] - f.box[1]] for f in candidates]
            indices = cv2.dnn.NMSBoxes(
                boxes, [f.confidence for f in candidates], max(0, self.threshold - 1e-7), self.nms_threshold
            )
            findings.extend(candidates[int(i)] for i in np.asarray(indices).flatten())
        return findings


class DetectorGroup:
    def __init__(self, specs, threshold=0.7):
        if not specs:
            raise ValueError("Configura al menos un modelo entrenado")
        self.detectors = [OnnxDetector(spec, threshold) for spec in specs]

    def detect(self, image):
        return [finding for detector in self.detectors for finding in detector.detect(image)]
