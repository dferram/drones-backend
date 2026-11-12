"""Replay de telemetría SITL registrada; no representa una grabación de cámara."""

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("data/sitl-postgres-report.json"))
    parser.add_argument("--output", type=Path, default=Path("data/sitl-demo.mp4"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    samples = report["samples"]
    if not samples:
        raise ValueError("No hay telemetría para reproducir")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), 2, (800, 600))
    if not writer.isOpened():
        raise RuntimeError("No se pudo crear MP4")
    origin = samples[0]

    def point(lat, lon):
        north = (lat - origin["latitude"]) * 111320
        east = (lon - origin["longitude"]) * 111320 * math.cos(math.radians(lat))
        return round(320 + east * 4), round(420 - north * 4)

    tracks = {}
    try:
        for sample in samples:
            image = np.full((600, 800, 3), (30, 24, 18), dtype=np.uint8)
            cv2.putText(
                image,
                "SITL TELEMETRY REPLAY - NO CAMERA FOOTAGE",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )
            mission = next(m for m in report["missions"] if m["id"] == sample["mission_id"])
            for wp in mission["waypoints"]:
                cv2.circle(image, point(wp["latitud"], wp["longitud"]), 7, (180, 180, 180), 1)
            track = tracks.setdefault(sample["mission_id"], [])
            track.append(point(sample["latitude"], sample["longitude"]))
            if len(track) > 1:
                cv2.polylines(image, [np.asarray(track, dtype=np.int32)], False, (210, 180, 60), 2)
            cv2.circle(image, track[-1], 8, (100, 240, 150), -1)
            lines = [
                f"Mission {sample['mission_id']} / {sample['state']}",
                f"Mode {sample['mode']} | Armed {sample['armed']}",
                f"Altitude {sample['relative_altitude_m']:.2f} m",
                sample["timestamp"],
            ]
            for index, line in enumerate(lines):
                cv2.putText(image, line, (20, 485 + index * 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1)
            writer.write(image)
    finally:
        writer.release()
    print(args.output)


if __name__ == "__main__":
    main()
