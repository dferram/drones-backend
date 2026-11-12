# CLAUDE.md — Plan de implementación

Backend del sistema de drones autónomos (UAQ). FastAPI + PostgreSQL + DroneKit/MAVLink.
Este documento es la guía de contexto y el plan de trabajo pendiente.

---

## 1. Estado actual del código

### Implementado y probado (111 tests, `pytest`)

| Área | Archivos clave | Notas |
|---|---|---|
| Auth + RBAC (ADMIN / GUARDIA) | `app/api/v1/endpoints/auth.py`, `app/api/deps.py`, `app/core/security.py` | Registro solo ADMIN; bootstrap con `python -m app.bootstrap_admin` |
| CRUD de misiones con waypoints | `app/api/v1/endpoints/missions.py`, `app/models/mission.py`, `app/schemas/mission.py` | Waypoints con orden único y consecutivo desde 1 |
| Ejecución de rutas dinámicas | `app/services/mission_service.py` | `POST /missions/{id}/start`, estados PROGRAMADA→EN_CURSO→FINALIZADA, progreso `waypoints_completados`, scheduler opcional (`MISSION_SCHEDULER_ENABLED=true`) |
| Cancelación en tiempo real | `mission_service.cancel()` | EN_CURSO→CANCELANDO con RTL confirmado; `confirm-landed` libera la reserva `vehiculo_activo` tras interrupciones/reinicios |
| Control manual de vuelo | `app/api/v1/endpoints/drone.py`, `app/services/drone_service.py` | `/connect`, `/takeoff`, `/rtl` con verificación de heartbeat, modo GUIDED, altura y desarmado |
| CI/CD | `.github/workflows/ci.yml`, `cd.yml` | Ruff + pytest en cada push; build Docker + smoke test HTTP |
| Simulación SITL | `scripts/run_sitl.sh`, `scripts/run_mavproxy.sh`, `docs/SITL_SIMULATION.md` | ArduPilot SITL + MAVProxy en `127.0.0.1:14550` |

### Stubs vacíos (0 líneas) — por implementar

- `app/api/v1/endpoints/alerts.py`, `telemetry.py`, `users.py`
- `app/models/alert.py`, `app/models/geofence.py`
- `app/services/alert_service.py`
- `app/schemas/alert.py`

No existe código de video, OpenCV, detección ni streaming en ningún archivo.

---

## 2. Convenciones del repo

- Respuestas/comentarios del código en español; nombres de modelos en español (`Mision`, `Ruta`, `Usuario`).
- Linter: Ruff (`ruff check app/`, `ruff format app/`) — CI falla si no pasa.
- Tests: SQLite en memoria vía `conftest.py`; el vehículo se sustituye por dobles (ver `tests/test_mission_execution.py` para el patrón de fake vehicle/hilo real).
- DroneKit es dependencia opcional con import lazy en `drone_service.py` — **nunca importar dronekit a nivel de módulo** fuera de ese archivo; los tests y la imagen Docker deben arrancar sin vehículo.
- Una sola instancia/worker de control: los locks de `MissionService` viven en proceso. La reserva `vehiculo_activo` (única, en BD) sobrevive reinicios.
- Migraciones con Alembic: crear revisión nueva por cada cambio de esquema; probar upgrade/downgrade conservando datos (ver `tests/test_migration_execution.py`).

### Comandos

```bash
source venv/bin/activate
pip install -r requirements.txt
docker-compose up -d && alembic upgrade head && python -m app.bootstrap_admin
uvicorn app.main:app --reload          # http://localhost:8000/docs
pytest -v                              # 111 tests, sin PostgreSQL
ruff check app/ && ruff format --check app/
scripts/run_sitl.sh                    # terminal 1
scripts/run_mavproxy.sh                # terminal 2
```

---

## 3. Plan de implementación (pendientes)

### Fase A — Cerrar evidencia de vuelo (bloqueante para el resto)

Objetivo: la aceptación pendiente de fases 1–3 de `docs/WORK_PLAN.md`.

- [ ] **A1. Demo SITL grabada**: levantar SITL + MAVProxy + API, conectar, crear 2 rutas distintas desde la API, ejecutar `POST /missions/{id}/start` sin tocar scripts, capturar llegada a waypoints (progreso en `GET /missions/{id}`), cancelación mid-flight con RTL confirmado, y aterrizaje. Guardar evidencia (video/capturas + salida de la API) en `docs/` o enlazarla desde el README.
- [ ] **A2. Prueba de integración PostgreSQL + SITL**: repetir el flujo completo contra PostgreSQL real (no SQLite): migraciones → bootstrap → crear misión → start → cancel → confirm-landed → reinicio de API con reserva pendiente → recuperación. Documentar resultado en `docs/WORK_PLAN.md`.
- [ ] **A3. Telemetría expuesta** (`endpoints/telemetry.py`, hoy vacío): `GET /api/v1/telemetry/` (GUARDIA y ADMIN) que devuelva lat/lon/alt relativa, modo, armado, batería, GPS fix y `last_heartbeat` desde `drone_service.vehicle`. Añadir método `get_telemetry()` a `DroneService` con las mismas guardas de `ensure_connected`. Tests con doble de vehículo.

### Fase B — Video: fuente simulada y streaming

- [ ] **B1. Servidor de streaming**: usar **MediaMTX** como servicio aparte en `docker-compose.yml` (RTSP ingest → WebRTC/HLS para el frontend). No retransmitir video desde FastAPI. Alternativa mínima para demo: endpoint MJPEG `GET /api/v1/stream` (multipart/x-mixed-replace) alimentado por el mismo pipeline — decidir según deadline, documentar la elección.
- [ ] **B2. Cámara simulada**: SITL no genera video. Implementar `app/services/vision/sources/` con dos fuentes tras una interfaz común (`read() -> frame`): (a) video de archivo/galleta de prueba (reproducción en loop, configurable con `VIDEO_SOURCE_URL`), (b) generador sintético de frames para tests. Si luego hay Gazebo con cámara, basta publicar su feed a MediaMTX vía ffmpeg y consumir el mismo RTSP.
- [ ] **B3. Streaming funcional + latencia**: cadena fuente → MediaMTX → consumo del pipeline → reproducción. Medir y documentar latencia end-to-end y comportamiento de reconexión. Ajustar codec/calidad (resolución, bitrate, keyframe interval) hasta latencia < ~1–2 s para WebRTC o documentar la obtenida con HLS.

### Fase C — Pipeline de procesamiento y detectores

Dependencias nuevas: `opencv-python-headless`, `numpy` (añadir a `requirements.txt`; headless para que funcione en Docker/CI).

- [ ] **C1. Pipeline de frames** (`app/services/vision/pipeline.py`): hilo/background task que lee de la fuente, aplica stride de frames configurable, ejecuta detectores registrados y emite eventos `Detection(tipo, confianza, bbox, frame, timestamp)`. Arranque/paro con el lifespan de FastAPI; desactivable con `VISION_ENABLED=false` (tests y CI sin cámara).
- [ ] **C2. Detector de personas**: interfaz `Detector.detect(frame) -> list[Detection]`. Implementación: YOLOv8n exportado a ONNX ejecutado con `cv2.dnn` (evita PyTorch/ultralytics como dependencia). Umbral de confianza y clases filtradas (person) configurables. Guardar el ONNX en `models/` o descargarlo en build — nunca commitear binarios grandes sin decidir dónde viven.
- [ ] **C3. Detector de humo**: empezar con heurística OpenCV (segmentación de color gris/blanco ascendente + análisis de textura/movimiento) documentando sus límites; dejar la interfaz lista para sustituir por un clasificador ONNX si la precisión no alcanza. Ambos detectores comparten la interfaz de C2.
- [ ] **C4. Regla de horario**: la detección de personas solo genera evento fuera del horario operativo (RF01). Parámetros `OPERATING_HOURS_START/END` en `app/core/config.py` (pydantic-settings), evaluados sobre la hora local configurable.

### Fase D — Alertas y disparo automático

- [ ] **D1. Modelo `Alerta`** (`app/models/alert.py`, hoy vacío): `id`, `tipo` (PERSONA_FUERA_HORARIO / HUMO), `estado`, `mision_id` (FK nullable), `latitud`, `longitud`, `confianza`, `evidencia_path`, `created_at`. Migración Alembic con upgrade/downgrade probado. Registrar en `app/models/__init__.py`.
- [ ] **D2. `alert_service` con deduplicación**: `create_alert(tipo, deteccion, telemetria)` que (a) adjunte telemetría actual del `drone_service` y misión activa del `mission_service`, (b) guarde snapshot JPEG de evidencia en disco (`data/evidence/`, fuera de git), (c) deduplique: misma clase dentro de ventana de tiempo/distancia → actualizar la existente en vez de crear duplicado.
- [ ] **D3. Endpoints** (`endpoints/alerts.py`): `GET /alerts/` con filtros (tipo, estado, rango de fechas) para GUARDIA y ADMIN; `GET /alerts/{id}` con evidencia. Registrar router en `app/api/v1/api.py`.
- [ ] **D4. Disparo automático**: conectar pipeline → `alert_service` dentro del mismo proceso (sin HTTP interno). Publicación a frontend vía polling del endpoint o WebSocket si el tiempo alcanza — para el sprint basta el endpoint.

### Fase E — Validación (reportes)

- [ ] **E1. Precisión de detectores**: `scripts/evaluate_detectors.py` + dataset etiquetado separado (carpeta `tests/data/eval/` con imágenes y labels; no reusar imágenes de desarrollo). Salida: precision/recall/F1, conteo de falsos positivos y negativos por detector → `docs/` como reporte.
- [ ] **E2. Tiempos end-to-end**: instrumentar t_captura_frame → t_detección → t_alerta_persistida; script o test que mida y reporte p50/p95 → `docs/`.
- [ ] **E3. CI/CD + docs**: los nuevos tests corren con el `pytest tests/` existente (marcar los que requieran OpenCV/modelo con un marker de pytest por si hay que excluirlos). Actualizar `docs/WORK_PLAN.md`, `docs/API.md` y la tabla de tests del README.

---

## 4. Decisiones de diseño ya tomadas (no re-debatir sin causa)

- **Un solo ejecutor de vuelo**: no crear segundo worker ni ejecutar misiones en paralelo; `vehiculo_activo` es la reserva exclusiva.
- **DroneKit lazy import**: los endpoints de vuelo deben fallar con 503 claro si no hay dronekit/vehículo, nunca romper el arranque.
- **Cancelación = señal + RTL confirmado**: `cancel()` nunca devuelve "cancelado" sin confirmar aterrizaje; estados terminales solo tras `is_grounded()`.
- **Timestamps**: columnas nuevas con `DateTime(timezone=True)` y `datetime.now(UTC)` (el esquema viejo usa naive UTC — mantener compatibilidad en validadores como `utc_schedule`).

## 5. Riesgos conocidos

- La imagen Docker actual instala todo `requirements.txt`; `opencv-python-headless` crece la imagen — aceptable, pero verificar el smoke test de `cd.yml` tras añadirla.
- El modelo ONNX debe descargarse en build o incluirse con LFS; no meter binarios al repo normal.
- La deduplicación de alertas necesita criterio explícito (ventana + distancia); definirlo en el código con constantes configurables, no hardcodear en la lógica.
- `httpx2` en `requirements.txt` parece dependencia accidental; revisar si puede eliminarse.
