"""Validación opt-in: arranca SU PROPIO SITL; nunca acepta un endpoint de vehículo externo."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path.home() / ".dronekit/sitl/copter-3.3/apm")
    parser.add_argument("--instance", type=int, default=24)
    parser.add_argument("--output", type=Path, default=Path("data/sitl-report.json"))
    args = parser.parse_args()
    if not args.binary.is_file() or not 1 <= args.instance <= 100:
        parser.error("Binario SITL o instancia inválidos")
    os.environ.update(
        SECRET_KEY=secrets.token_hex(32),
        DATABASE_URL="sqlite:///:memory:",
        MISSION_SCHEDULER_ENABLED="false",
        VIDEO_ENABLED="false",
        VISION_ENABLED="false",
    )
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    from app.api import deps
    from app.api.v1.endpoints import drone as drone_endpoint
    from app.api.v1.endpoints import telemetry as telemetry_endpoint
    from app.core.security import get_password_hash
    from app.main import app
    from app.models.user import Rol, Usuario
    from app.services.drone_service import DroneService
    from app.services.mission_service import MissionService, get_mission_service

    report = {"simulator": str(args.binary), "missions": [], "samples": [], "passed": False}
    process = engine = admin_engine = service = None
    driver = DroneService()
    schema = "sitl_" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="drones-sitl-") as folder:
        folder = Path(folder)
        url = f"sqlite:///{folder / 'test.db'}"
        if os.getenv("TEST_POSTGRES_URL"):
            base = make_url(os.environ["TEST_POSTGRES_URL"])
            admin_engine = create_engine(base)
            with admin_engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            url = base.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
        report["database"] = "postgresql" if admin_engine else "sqlite"
        log = (folder / "sitl.log").open("w")
        try:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                env={**os.environ, "DATABASE_URL": url},
                check=True,
                capture_output=True,
                timeout=60,
            )
            process = subprocess.Popen(
                [
                    str(args.binary.resolve()),
                    "--home=20.70428,-100.44358,1800,353",
                    "--model=quad",
                    "--wipe",
                    f"--instance={args.instance}",
                    "--speedup=1",
                ],
                cwd=folder,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            time.sleep(2)
            if process.poll() is not None:
                raise RuntimeError("SITL no pudo arrancar; revisar puertos y binario")
            assert driver.connect(f"tcp:127.0.0.1:{5760 + args.instance * 10}")
            # Parámetros oficiales que acompañan al binario, solo en este SITL recién creado.
            defaults = args.binary.parent / "default.parm"
            if defaults.is_file():
                for line in defaults.read_text().splitlines():
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    name, value = line.split()[:2]
                    if name in driver.vehicle.parameters:
                        driver.vehicle.parameters[name] = float(value)
            driver.vehicle.parameters["ARMING_CHECK"] = 0
            driver.vehicle.parameters["FENCE_ENABLE"] = 0
            driver.vehicle.parameters["RTL_ALT"] = 500
            driver.vehicle.parameters["RTL_LOIT_TIME"] = 1000
            deadline = time.monotonic() + 90
            while not (driver.vehicle.is_armable and driver.vehicle.gps_0.fix_type >= 3):
                if time.monotonic() > deadline:
                    raise TimeoutError("SITL no quedó listo para vuelo")
                time.sleep(1)
            time.sleep(10)
            engine = create_engine(url, **({"connect_args": {"check_same_thread": False}} if not admin_engine else {}))
            sessions = sessionmaker(bind=engine)
            with sessions.begin() as db:
                role = Rol(nombre="ADMIN")
                db.add(role)
                db.flush()
                db.add(
                    Usuario(
                        nombre="SITL Test",
                        email="sitl@example.com",
                        rol_id=role.id,
                        password_hash=get_password_hash("Local-SITL-Test-123!"),
                        activo=True,
                    )
                )
            service = MissionService(sessions, driver)

            def get_db():
                with sessions() as db:
                    yield db

            app.dependency_overrides[deps.get_db] = get_db
            app.dependency_overrides[get_mission_service] = lambda: service
            original_drone, original_telemetry = drone_endpoint.drone_service, telemetry_endpoint.drone_service
            drone_endpoint.drone_service = telemetry_endpoint.drone_service = driver
            try:
                with TestClient(app) as client:
                    login = client.post(
                        "/api/v1/auth/login", json={"email": "sitl@example.com", "password": "Local-SITL-Test-123!"}
                    )
                    assert login.status_code == 200, login.text
                    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                    for index, (north, east, cancel) in enumerate(
                        [(0.00008, 0, False), (0, 0.00012, False), (0.0005, 0.0005, True)], 1
                    ):
                        waypoints = [
                            dict(
                                orden_waypoint=1, latitud=20.70428 + north, longitud=-100.44358 + east, altitud_metros=5
                            ),
                            dict(orden_waypoint=2, latitud=20.70428, longitud=-100.44358, altitud_metros=5),
                        ]
                        created = client.post(
                            "/api/v1/missions/",
                            headers=headers,
                            json={"nombre": f"SITL route {index}", "waypoints": waypoints},
                        )
                        assert created.status_code == 201, created.text
                        mission_id = created.json()["id"]
                        started = client.post(f"/api/v1/missions/{mission_id}/start", headers=headers)
                        assert started.status_code == 202, started.text
                        deadline = time.monotonic() + 240
                        requested = False
                        while time.monotonic() < deadline:
                            state = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()
                            telemetry = client.get("/api/v1/telemetry/", headers=headers)
                            assert telemetry.status_code == 200, telemetry.text
                            sample = {"mission_id": mission_id, "state": state["estado"], **telemetry.json()}
                            report["samples"].append(sample)
                            if cancel and not requested and sample["relative_altitude_m"] >= 3:
                                response = client.post(f"/api/v1/missions/{mission_id}/cancel", headers=headers)
                                assert response.status_code == 200, response.text
                                requested = True
                            if state["estado"] in ("FINALIZADA", "CANCELADA", "FALLIDA", "RECUPERACION"):
                                break
                            time.sleep(0.5)
                        report["missions"].append(state)
                        print(json.dumps(state), flush=True)
                        assert state["estado"] == ("CANCELADA" if cancel else "FINALIZADA"), state
                        assert driver.is_grounded()
                        assert state["finalizada_at"] is not None
                        if not cancel:
                            assert state["waypoints_completados"] == 2
                    report["passed"] = True
            finally:
                drone_endpoint.drone_service, telemetry_endpoint.drone_service = original_drone, original_telemetry
                app.dependency_overrides.clear()
        except Exception as exc:
            report["error"] = str(exc)
            raise
        finally:
            if service:
                service.shutdown()
            if driver.vehicle:
                try:
                    if not driver.is_grounded():
                        driver.return_to_launch()
                        driver.wait_landed(timeout=120)
                except Exception as exc:
                    report["cleanup_error"] = str(exc)
                driver.close()
            if process:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            log.close()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            args.output.with_suffix(".log").write_text((folder / "sitl.log").read_text())
            if engine:
                engine.dispose()
            if admin_engine:
                with admin_engine.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                admin_engine.dispose()


if __name__ == "__main__":
    main()
