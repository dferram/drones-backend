"""Descarga opt-in de un modelo de personas; revisión y SHA-256 fijados."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

REVISION = "91e55d55d5b0cbf13fb661dea4f27e270c841428"
URL = f"https://huggingface.co/cabelo/yolov8/resolve/{REVISION}/yolov8n.onnx"
SHA256 = "c03e8dc50385b49f150a8de1b3fa6f3f8a0ba0ce2a458a353179c084f8012f35"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("models"))
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    path = args.directory / "yolov8n.onnx"
    if path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=120) as response:
            data = response.read(30 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Checksum incorrecto; no se instaló ni sobrescribió el modelo")
    if not path.exists():
        with path.open("xb") as handle:
            handle.write(data)
    manifest = args.directory / "person-model.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                [{"path": str(path), "class_count": 80, "input_size": 640, "labels": {"0": "PERSONA"}}], indent=2
            )
            + "\n"
        )
    print(f"Modelo verificado: {path}; manifiesto: {manifest}")


if __name__ == "__main__":
    main()
