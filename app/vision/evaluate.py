"""python -m app.vision.evaluate --models models.json --dataset labels.jsonl --output report.json"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np

from app.schemas.vision import ModelSpec
from app.vision.detector import DetectorGroup


def iou(a, b):
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union > 0 else 0


def evaluate(detector, records, root, threshold=0.5):
    counts = {tipo: {"tp": 0, "fp": 0, "fn": 0} for tipo in ("PERSONA", "HUMO")}
    latencies = []
    for record in records:
        image = cv2.imread(str(root / record["image"]))
        if image is None:
            raise ValueError(f"Imagen no legible: {record['image']}")
        truth = record["annotations"]
        for item in truth:
            box = item["box"]
            if item["tipo"] not in counts or len(box) != 4 or not all(np.isfinite(box)):
                raise ValueError("Etiqueta de evaluación inválida")
            if not 0 <= box[0] < box[2] <= image.shape[1] or not 0 <= box[1] < box[3] <= image.shape[0]:
                raise ValueError("Bounding box de evaluación inválido")
        start = time.perf_counter()
        predictions = detector.detect(image)
        latencies.append((time.perf_counter() - start) * 1000)
        unmatched = set(range(len(truth)))
        for prediction in sorted(predictions, key=lambda value: value.confidence, reverse=True):
            candidates = [
                (iou(prediction.box, truth[i]["box"]), i) for i in unmatched if truth[i]["tipo"] == prediction.tipo
            ]
            score, index = max(candidates, default=(0, -1))
            if score >= threshold:
                unmatched.remove(index)
                counts[prediction.tipo]["tp"] += 1
            else:
                counts[prediction.tipo]["fp"] += 1
        for index in unmatched:
            counts[truth[index]["tipo"]]["fn"] += 1
    if not latencies:
        raise ValueError("El conjunto de evaluación está vacío")
    for result in counts.values():
        tp, fp, fn = result["tp"], result["fp"], result["fn"]
        result["precision"] = tp / (tp + fp) if tp + fp else None
        result["recall"] = tp / (tp + fn) if tp + fn else None
    return {
        "images": len(latencies),
        "iou_threshold": threshold,
        "classes": counts,
        "inference_p50_ms": float(np.percentile(latencies, 50)),
        "inference_p95_ms": float(np.percentile(latencies, 95)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confidence", type=float, default=0.7)
    args = parser.parse_args()
    if not 0 < args.confidence <= 1:
        parser.error("--confidence debe estar entre 0 y 1")
    specs = [ModelSpec.model_validate(spec) for spec in json.loads(args.models.read_text())]
    records = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    result = evaluate(DetectorGroup(specs, args.confidence), records, args.dataset.parent)
    result["confidence_threshold"] = args.confidence
    result["dataset_sha256"] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    result["models"] = [
        {"path": spec.path, "sha256": hashlib.sha256(Path(spec.path).read_bytes()).hexdigest()} for spec in specs
    ]
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
