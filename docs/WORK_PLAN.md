# Plan de trabajo y evidencia

Revisión inicial: 25 de octubre de 2026. Actualizada: 27 de octubre de 2026. Alcance: este repositorio backend.

| Fase | Entregable | Estado |
|---|---|---|
| 1. Base estable | Permisos, configuración obligatoria, bootstrap local, contenedor verificable y demo SITL | En curso |
| 2. Misiones dinámicas | Ejecutor de waypoints persistidos, inicio por API y horario, progreso y estados | Implementada; validación SITL pendiente |
| 3. Telemetría y cancelación | Estado del vehículo, interrupción con RTL confirmado, tiempos máximos y desconexiones | Implementadas cancelación con RTL, tiempos máximos, recuperación y consulta HTTP de telemetría; validación SITL pendiente |
| 4. Integración de vuelo | Pruebas PostgreSQL + SITL, documentación y demo integrada | Pendiente; existen pruebas API + SQLite |
| 5. Video | Fuente simulada, servidor y reproducción, reconexión y medición de latencia | Parcial: fuente sintética/archivo, MJPEG autenticado y reconexión implementados; faltan cámara y latencia end-to-end |
| 6. Detección | Pipeline de frames, personas, humo y evaluación con datos separados | Pendiente |
| 7. Alertas y validación | Persistencia de eventos, reglas, deduplicación, evidencia y tiempos end-to-end | Parcial: ingesta, eventos y reglas existentes; deduplicación implementada; faltan entrega de alertas y mediciones |

## Cambios de fase 1

- Registro de usuarios restringido a ADMIN. Bootstrap local con `python -m app.bootstrap_admin`, tras las migraciones. No promueve cuentas existentes y rechaza un segundo bootstrap cuando ya existe ADMIN.
- Conexión y despegue restringidos a ADMIN; RTL permitido a ADMIN y GUARDIA.
- Altitud de despegue finita, entre 2 y 200 metros.
- `SECRET_KEY` obligatoria, mínimo 32 caracteres, sin valor de respaldo en código ni secreto en la plantilla.
- Docker instala `requirements.txt`, ejecuta como usuario sin privilegios y excluye `.env`, entornos y artefactos locales del contexto.
- Workflow de contenedor comprueba arranque HTTP. No publica ni despliega.
- Dependencia `future` declarada para que DroneKit pueda importar `past.builtins`; CI comprueba también la disponibilidad del servicio de vuelo sin conectar a un vehículo.
- Pruebas aisladas de la configuración local: clave efímera y SQLite en memoria.

## Verificación

- Suite: 70 pruebas aprobadas en el entorno local fuera del sandbox. Dentro del sandbox, TestClient se bloquea antes de ejecutar las peticiones.
- Ruff: lint y formato aprobados.
- Imagen Docker construida y respuesta HTTP 200 comprobada como usuario sin privilegios, sin copiar `.env` ni `.aws`. Suite de 70 pruebas aprobada también en Python 3.11 dentro del contenedor.
- Tras añadir `future`, la imagen se reconstruyó y se verificaron nuevamente la importación de DroneKit y el arranque HTTP; no se conectó a ningún vehículo.
- Los tests de permisos sustituyen el servicio de vuelo; no mandan comandos a un dron.
- La fase 1 no se cierra hasta reproducir y registrar la demo SITL. No hay evidencia nueva de vuelo ni de aterrizaje confirmado.
- El smoke test HTTP del contenedor no valida migraciones, PostgreSQL ni el enlace SITL.

## Próximos criterios de aceptación

1. Completar fase 1: levantar un SITL aislado, ejecutar la demo, comprobar llegada y aterrizaje y registrar evidencia. Mantener desactivaciones de geofence y prearmado limitadas a simulación.
2. Fases 2 y 3: crear dos rutas diferentes desde la API y ejecutarlas sin editar scripts; confirmar progreso, fin y cancelación mediante datos del simulador. Incorporar exclusión de vuelos simultáneos y límites de espera.
3. Fase 4: comprobar flujo completo y fallos con PostgreSQL y SITL, incluyendo migraciones y reinicios.
4. Fase 5: reproducir video continuo y documentar reconexión y latencia.
5. Fase 6: reportar precisión, recall y falsos positivos por detector con datos de evaluación independientes.
6. Fase 7: generar una alerta consultable con misión, ubicación, tiempo y evidencia; medir latencias p50/p95 y evitar alertas duplicadas.

No se asignan fechas hasta conocer disponibilidad del equipo y fuente de video. El bloque de video puede avanzar en paralelo al vuelo tras acordar contratos de integración.


## Avance de fase 2

Implementado el ejecutor de rutas persistidas, inicio manual por API, progreso y resultados en BD, exclusión de vuelos simultáneos y planificador opcional. La migración `6bf21ac304de` añade una reserva exclusiva del vehículo que se conserva si no se confirma aterrizaje. Se adelantó la cancelación mínima de fase 3 para poder interrumpir rutas y recuperar reservas tras reinicios.

La migración se verificó en SQLite con upgrade, downgrade y nuevo upgrade conservando una misión previa. El flujo de vuelo está probado con dobles de vehículo e hilo real; todavía no hay evidencia nueva de SITL ni integración PostgreSQL + SITL. Las fases 1 y 2 conservan pendiente esa aceptación de vuelo. Instrucciones en [MISSION_EXECUTION.md](MISSION_EXECUTION.md).

Verificación de fase 2: 111 pruebas aprobadas localmente; Ruff y formato aprobados. Imagen `drones-backend:phase2-review` construida localmente.

## Revisión contra la captura de Notion — 27 de octubre de 2026

Fuente: captura proporcionada y código local; no se consultó ni modificó Notion.
Los estados siguientes distinguen implementación de validación en simulador.

| Pendiente de la captura | Evidencia / estado actual |
|---|---|
| MVP circuito cerrado y entorno de simulación | Scripts y guía SITL existentes; falta registrar demo y aterrizaje verificable |
| Conexión dron-backend | Servicio DroneKit existente; consulta HTTP de telemetría añadida en esta revisión |
| Configurar CI/CD | Workflows de lint, pruebas y smoke de contenedor existentes; sin despliegue automático |
| Demo del sprint 1 | Pendiente de ejecutar y grabar |
| Rutas dinámicas desde backend | Implementadas con waypoints persistidos, planificador y progreso; aceptación SITL pendiente |
| Cancelación/interrupción | Implementada con RTL y reserva hasta aterrizaje; aceptación SITL pendiente |
| Pruebas de integración de misiones | API + SQLite y dobles de vehículo existentes; falta PostgreSQL + SITL |
| Actualizar CI/CD y documentar | Corregidos errores que bloqueaban importación/lint y fixtures; nuevo contrato de telemetría documentado |
| Servidor de streaming, cámara simulada y stream funcional | Fuente sintética/archivo y MJPEG por API implementados; cámara de Gazebo y reproductor pendientes |
| Pipeline de procesamiento de frames | Captura, resize y JPEG implementados; consumidor de inferencia pendiente |
| Detectores de personas y humo | Pendientes; recibir etiquetas por API no equivale a detectar imágenes |
| Conexión detección-backend | Ingesta `/detections/ingest` existente con persistencia |
| Disparo automático de eventos | Reglas de humo y persona nocturna y deduplicación implementadas; pendiente entrega de alertas |
| Pruebas de precisión y ajuste | Pendientes de modelos y conjunto de evaluación |
| Pruebas end-to-end de tiempos | Pendientes de pipeline completo; no hay mediciones p50/p95 |

### Correcciones y desarrollo de esta revisión

- Eliminados bloques duplicados en router, exports y fixtures que impedían
  importar la API o contaminaban las pruebas con estado compartido.
- Restaurada la carga opcional de DroneKit: una importación previa al `try`
  impedía arrancar sin la dependencia de simulación.
- Añadida migración de unión `91ea260427ab` para las ramas de ejecución y
  detecciones. Aplicar `alembic upgrade head` al preparar el entorno; esta revisión
  solo ejecuta migraciones en bases temporales de prueba.
- Añadido `GET /api/v1/telemetry/` para ADMIN/GUARDIA, con heartbeat válido de
  hasta cinco segundos y sensores desconocidos representados como `null`.
- Corregida la prueba de actualización de eventos para crear sus propios datos.
- Homogeneizados imports y formato para cumplir los checks existentes de CI.

### Trabajo que sigue abierto

1. Validar dos rutas y cancelación con PostgreSQL + SITL; grabar demo.
2. Conectar el productor de visión a la ingesta autenticada; revisar zona horaria
   de registros históricos y proporcionar identificadores de vuelo distintos.
3. Integrar consumidor de inferencia y fuente de cámara con el pipeline de video existente.
4. Integrar modelos, evaluar precisión y medir latencia del flujo completo.

### Verificación del 27 de octubre

- Suite completa: **130 pruebas aprobadas** fuera del sandbox (TestClient se
  bloquea dentro de él); una advertencia existente por `datetime.utcnow()`.
- Después se amplió la prueba de migraciones a tres puntos de partida:
  **3 casos aprobados**, incluyendo las dos ramas y su ancestro común, con
  upgrade/downgrade y conservación de la misión previa. La suite ahora contiene
  132 casos; los dos añadidos se verificaron en esa ejecución específica.
- `ruff check .`, `ruff format --check .` y `git diff --check`: aprobados.
- No se ejecutaron vuelos, demo, integración PostgreSQL ni un nuevo build Docker.

## Continuación: ingesta y eventos

- Ingesta restringida a ADMIN, tipos PERSONA/HUMO, validación de coordenadas,
  confianza, referencias y timestamps con zona. Ejemplo Postman actualizado.
- Normalización a UTC y regla nocturna configurable mediante zona IANA. Filtros
  y respuestas de eventos usan UTC; rangos de fechas invertidos devuelven 422.
- Agrupación de evidencia por tipo, vuelo, ventana fija y distancia al primer
  frame. Mantiene cada detección y excluye eventos resueltos.
- Rollback transaccional y exclusión entre procesos con PostgreSQL.
- Prueba opt-in de migraciones e ingesta concurrente real; servicio PostgreSQL 16
  incorporado al workflow CI.

No se implementaron aún captura de evidencia, entrega de alertas, streaming ni
modelos de visión. La deduplicación de incidentes no elimina reenvíos del mismo
frame. El uso del token ADMIN es el contrato actual; un rol exclusivo de productor
puede incorporarse cuando exista ese servicio.

Verificación de esta continuación:

- Suite completa con PostgreSQL temporal: **161 pruebas aprobadas**, incluida
  migración e ingesta desde cuatro procesos independientes (ocho detecciones,
  un evento). La instancia temporal quedó apagada.
- Tras añadir normalización de filtros de fechas y serialización UTC de eventos:
  **30 pruebas de detecciones/eventos aprobadas**. La suite contiene ahora 163
  casos; los dos nuevos se verificaron en esa ejecución específica.
- Lint, formato y revisión de whitespace aprobados. El workflow se actualizó,
  pero no se ejecutó GitHub Actions desde esta sesión.

## Continuación: video y procesamiento de frames

- Servicio OpenCV con fuente sintética animada o archivo local en bucle.
- Un buffer del frame más reciente, fps/tamaño/calidad limitados y reintentos.
- Endpoints autenticados de estado, snapshot JPEG y stream MJPEG.
- Detección de frames caducados y cierre acotado de conexiones de stream.
- Inicio/cierre integrado al lifespan, dependencias y configuración documentadas
  en [VIDEO.md](VIDEO.md).

La fuente sintética no es una cámara de Gazebo. No se implementaron aún modelos
de detección, captura de evidencia persistente ni reproducción web. La métrica
de procesamiento no sustituye el reporte de latencia end-to-end pendiente.

Verificación de video:

- Suite completa: **186 pruebas aprobadas y 1 omitida** (PostgreSQL opt-in sin
  `TEST_POSTGRES_URL`; ya se verificó en la continuación anterior).
- Incluye 16 pruebas de video y 8 validaciones adicionales de configuración.
- Ruff lint, formato y `git diff --check` aprobados.
- No se ejecutó un nuevo build Docker ni vuelos SITL.
