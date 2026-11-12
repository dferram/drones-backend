<div align="center">

  <img src="https://upload.wikimedia.org/wikipedia/commons/4/4b/Logo_UAQ.png" alt="UAQ Logo" height="120px">

### Sistema de Drones Autónomos

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)

---

Proyecto integral de Backend, Simulación y Control desarrollado para la Facultad de Informática de la Universidad Autónoma de Querétaro (UAQ).

</div>

---

## Tabla de Contenidos

- [Documentación](#documentación)
- [Inicio Rápido](#inicio-rápido)
- [Miembros del Equipo](#miembros-del-equipo)
- [Descripción de Arquitectura](#descripción-de-arquitectura)
- [Product Backlog (Priorizado)](#product-backlog-priorizado)
- [Cronograma de Ejecución (Roadmap)](#cronograma-de-ejecución-roadmap)
- [Sprint 1: Arquitectura Base, Entornos y MVP](#sprint-1-arquitectura-base-entornos-y-mvp)

---

## Documentación

| Documento | Descripción |
|---|---|
| [📖 API Reference](docs/API.md) | Todos los endpoints: request, response, códigos de error, permisos por rol |
| [🛠 Guía de Desarrollo](docs/DEVELOPMENT.md) | Instalación, entorno local, tests, linter, migraciones, Git workflow |
| [🏗 Arquitectura](docs/ARCHITECTURE.md) | Diagramas del sistema, modelo de datos, flujo de autenticación, stack |
| [🚀 Despliegue](docs/DEPLOYMENT.md) | Docker, docker-compose, producción, variables de entorno |
| [🛸 Simulación SITL](docs/SITL_SIMULATION.md) | ArduPilot SITL + MAVProxy + DroneKit para pruebas sin hardware |

---

## Inicio Rápido

```bash
# 1. Clonar y entrar
git clone https://github.com/AngelCenArr/drones-backend.git
cd drones-backend

# 2. Entorno virtual y dependencias
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env   # edita DATABASE_URL y SECRET_KEY (openssl rand -hex 32)

# 4. Levantar la DB
docker-compose up -d
alembic upgrade head
python -m app.bootstrap_admin  # crea el primer ADMIN de forma local

# 5. Correr el servidor
uvicorn app.main:app --reload
# → http://localhost:8000/docs

# 6. Ejecutar los tests (no requiere PostgreSQL)
pytest
# La suite incluye pruebas de API, permisos, configuración y bootstrap.
```

> Para instrucciones detalladas ver la [Guía de Desarrollo](docs/DEVELOPMENT.md).

---

## Guía de Desarrollo Local

### Requisitos Previos

| Herramienta | Versión mínima | Notas |
|---|---|---|
| Python | 3.11+ | Se recomienda 3.12 o superior |
| PostgreSQL | 15+ | Requerido para desarrollo y producción |
| Docker + Compose | — | Opcional, para levantar la DB rápidamente |
| Git | — | — |

---

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/AngelCenArr/drones-backend.git
cd drones-backend

# 2. Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

### Variables de Entorno

Copia el archivo de ejemplo y edita los valores:

```bash
cp .env.example .env
```

| Variable | Descripción | Ejemplo |
|---|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL | `postgresql://user:pass@localhost:5432/drone_db` |
| `SECRET_KEY` | Clave secreta para firmar JWT | cadena aleatoria de 64 chars |
| `ALGORITHM` | Algoritmo de firma JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token en minutos | `480` |

> **Nota:** El archivo `.env` está en el `.gitignore` — nunca lo subas al repositorio.

#### Levantar la base de datos con Docker (opcional)

```bash
docker-compose up -d
```

#### Aplicar migraciones

```bash
alembic upgrade head
```

---

### Correr el Servidor

```bash
# Activar el entorno virtual primero
source venv/bin/activate

# Modo desarrollo (con hot-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El servidor queda disponible en:

| URL | Descripción |
|---|---|
| `http://localhost:8000` | Endpoint raíz (`{"status": "ok"}`) |
| `http://localhost:8000/docs` | Swagger UI interactivo |
| `http://localhost:8000/redoc` | Documentación ReDoc |
| `http://localhost:8000/api/v1/` | Versión 1 de la API |

---

### Ejecutar los Tests

Los tests usan una **base de datos SQLite en memoria** — no requieren PostgreSQL ni ninguna configuración extra.

```bash
# Activar el entorno virtual primero
source venv/bin/activate

# Correr toda la suite
pytest

# Con reporte detallado (ya configurado por defecto)
pytest -v

# Correr solo un archivo
pytest tests/test_auth.py
pytest tests/test_missions.py
pytest tests/test_security.py

# Correr una clase o test específico
pytest tests/test_auth.py::TestLogin
pytest tests/test_auth.py::TestLogin::test_login_admin_success

# Con reporte de cobertura (requiere pytest-cov)
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

#### Suite de tests actual

| Archivo | Tests | Qué cubre |
|---|---|---|
| `tests/test_auth.py` | 15 | `POST /register`, `POST /login`, `GET /me` — éxito, errores de validación, RBAC |
| `tests/test_missions.py` | 24 | CRUD completo de misiones — creación, listado, filtros, edición, cancelación, permisos |
| `tests/test_security.py` | 9 | Hashing bcrypt (salt único, verify) y tokens JWT (subject, expiración, firma inválida) |
| `tests/test_access.py` | 19 | Permisos de vuelo y registro, validación de altura y bootstrap |
| `tests/test_config.py` | 3 | Clave JWT obligatoria y longitud mínima |
| `tests/test_drone_navigation.py` | 9 | Navegación, tiempos máximos y telemetría |
| `tests/test_mission_execution.py` | 31 | Ejecución, cancelación, horarios, recuperación y permisos |
| `tests/test_migration_execution.py` | 1 | Migración conservando datos existentes |
| **Total** | **111** | |

**Resultado esperado:**

```
==================== 111 passed ====================
```

#### Estrategia de testing

- **DB aislada**: cada test usa SQLite en memoria — sin efectos secundarios entre tests.
- **Roles pre-seeded**: `conftest.py` crea los roles `ADMIN` y `GUARDIA` automáticamente.
- **Sin dependencias externas**: no requiere PostgreSQL, Redis ni dronekit para correr los tests.

---

### Linter

El proyecto usa [Ruff](https://docs.astral.sh/ruff/) para linting y formato:

```bash
# Verificar errores
ruff check app/

# Corregir automáticamente
ruff check app/ --fix

# Formatear el código
ruff format app/
```

---

### Estructura del Proyecto

```
drones-backend/
│
├── app/                          # Código fuente principal
│   ├── main.py                   # Punto de entrada FastAPI
│   ├── api/
│   │   ├── deps.py               # Dependencias compartidas (get_db, RBAC)
│   │   └── v1/
│   │       ├── api.py            # Router principal v1
│   │       └── endpoints/
│   │           ├── auth.py       # POST /register, /login, GET /me
│   │           ├── missions.py   # CRUD de misiones
│   │           ├── drone.py      # Control de vuelo (connect, takeoff, RTL)
│   │           ├── alerts.py     # (en desarrollo)
│   │           ├── telemetry.py  # (en desarrollo)
│   │           └── users.py      # (en desarrollo)
│   ├── core/
│   │   ├── config.py             # Configuración vía pydantic-settings
│   │   └── security.py           # JWT y bcrypt
│   ├── db/
│   │   ├── base_class.py         # Base declarativa de SQLAlchemy
│   │   └── session.py            # Engine y SessionLocal
│   ├── models/                   # Modelos ORM (tablas)
│   │   ├── user.py               # Usuario, Rol, Permiso
│   │   └── mission.py            # Mision, Ruta (waypoints)
│   ├── schemas/                  # Schemas Pydantic (request / response)
│   │   ├── user.py
│   │   ├── mission.py
│   │   └── token.py
│   └── services/
│       ├── drone_service.py      # Wrapper de DroneKit (import lazy)
│       └── mission_service.py    # (en desarrollo)
│
├── alembic/                      # Migraciones de base de datos
│   └── versions/
│
├── tests/                        # Suite de tests
│   ├── conftest.py               # Fixtures: DB SQLite, TestClient, usuarios
│   ├── test_auth.py              # Tests de autenticación
│   ├── test_missions.py          # Tests de misiones
│   └── test_security.py          # Tests unitarios de seguridad
│
├── scripts/
│   ├── drone_backend.py          # Script de integración DroneKit
│   ├── run_mavproxy.sh           # Lanzar MAVProxy con mapa UAQ
│   └── run_sitl.sh               # Lanzar simulador ArduPilot SITL
│
├── simulator/                    # Archivos generados por SITL (ignorados en git)
│   ├── mav.parm
│   ├── eeprom.bin
│   └── mav.tlog
│
├── docs/
│   └── SITL_SIMULATION.md        # Guía de configuración del simulador
│
├── .env                          # Variables de entorno locales (NO subir a git)
├── .env.example                  # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt              # Dependencias del proyecto
├── pyproject.toml                # Configuración de Ruff y Pytest
├── Dockerfile
└── docker-compose.yml            # PostgreSQL para desarrollo local
```

---

## Miembros del Equipo

- **Ángelica Cenobio** *(Scrum Master / DEV 2: Facilitación de ceremonias, mitigación de impedimentos, desarrollo de lógica de negocio en Backend y Arquitectura de Datos).*
- **Lu Álvarez** *(Product Owner / DEV 3: Gestión y priorización del Product Backlog, validación de criterios de aceptación, diseño de interfaz y desarrollo Frontend/Móvil).*
- **Fernando Ramírez** *(DEV 1: Desarrollo de módulos de control de vuelo, simulación, integración de hardware y automatización de despliegues CI/CD).*

---

## Descripción de Arquitectura

El presente repositorio agrupa el código fuente correspondiente a las capas de **Backend, Integración en Tiempo Real (Simulación y Control de Vuelo)** y la infraestructura **DevOps** del sistema de drones autónomos. 

La plataforma está diseñada para la ejecución de vuelos autónomos mediante el control estructurado de misiones, soportando transmisión de video de baja latencia, análisis en tiempo real basado en visión por computadora (detección de personas y presencia de humo) y mecanismos criptográficos para el almacenamiento seguro de la telemetría y material audiovisual.

---

## Product Backlog (Priorizado)

### Alta Prioridad
*   **RNF08 / RF04:** Implementación de vuelo autónomo básico en circuito cerrado (navegación multipunto) y ejecución de misiones programadas.
*   **RF11:** Control de acceso basado en roles (RBAC) para la plataforma de administración.
*   **RF01:** Módulo de visión computacional para la detección de personas fuera de horarios operativos.
*   **RF02 / RF03:** Sistema de mensajería para alertas en tiempo real con recolección de evidencia (captura de imagen, metadatos de tiempo y geolocalización).
*   **[Sin ID]:** Integración de modelo de clasificación de imágenes para detección de humo.
*   **RF06:** Protocolo de transmisión bidireccional y visualización de video en vivo.
*   **RNF03:** Implementación de cifrado en reposo para el almacenamiento del flujo de video.
*   **[Sin ID]:** Ejecución de pruebas de integración continua y estabilización del sistema para entrega en producción.

### Media Prioridad
*   **RF07:** Grabación continua y delegación de almacenamiento a repositorio seguro.
*   **RF05:** Configuración de perímetros virtuales restrictivos (Geofencing).
*   **RF08:** Automatización de purga de datos audiovisuales (política de retención a 30 días).
*   **RF09:** Implementación de bitácora transaccional e inmutable de telemetría de vuelo.
*   **RF10:** Registro y auditoría de eventos de acceso y mutación de estado.
*   **RNF04:** Protocolos de tolerancia a fallos en la capa de red (comunicación dron-estación base).
*   **RNF02 / RNF07:** Restricciones operativas a nivel software para cumplimiento normativo (límites de altitud y peso).
*   **RNF05:** Optimización de tiempos de respuesta en la interfaz web y móvil.

### Baja Prioridad
*   **RNF06:** API de integración para acoplamiento con infraestructura física (base de carga o helipuerto automatizado).

---

## Cronograma de Ejecución (Roadmap)

| Sprint | Hito Principal | Descripción de Entregables |
| :---: | :--- | :--- |
| **1** | **Fundamentos Arquitectónicos** | Definición de infraestructura, aprovisionamiento de entornos, MVP de vuelo autónomo y modelo de seguridad RBAC. |
| **2** | **Sistemas de Navegación** | Módulos de control y orquestación de misiones programadas. |
| **3** | **Análisis de Video (Personas)** | Integración de IA para detección de personas fuera de horario. |
| **4** | **Análisis de Video (Humo)** | Detección de humo en el procesamiento del flujo de imágenes. |
| **5** | **Sistema de Notificaciones** | Motor de reglas para generación de alertas con recolección de metadatos. |
| **6** | **Streaming** | Transmisión y visualización de video en tiempo real. |
| **7** | **Persistencia Segura** | Almacenamiento continuo con encriptación en reposo. |
| **8** | **Navegación Restringida** | Implementación del módulo de Geofencing y zonas de exclusión. |
| **9** | **Ciclo de Vida de Datos** | Política de retención (30 días) y auditoría inmutable de bitácoras. |
| **10** | **Trazabilidad y Usabilidad** | Auditoría integral de accesos y optimización de interacción de usuario. |
| **11** | **Estabilización Final** | Pruebas de tolerancia a fallos, revisión de hardware, documentación técnica y despliegue final. |

---

## Sprint 1: Arquitectura Base, Entornos y MVP

**Objetivo de la Iteración:**
Aprovisionar la infraestructura fundacional del proyecto, configurando los entornos de desarrollo e integración. Establecer el esquema de persistencia inicial (RBAC) y desplegar un Prototipo Mínimo Viable (MVP) para la simulación de vuelo autónomo en un circuito delimitado.

**Criterios de Aceptación (DoD):**
- [ ] Todo el código fuente está versionado en el repositorio principal, contando con al menos un Code Review (PR) aprobado.
- [ ] El simulador SITL ejecuta exitosamente una misión programada (trayectoria de ida y vuelta) sin intervención telemétrica manual.
- [ ] Flujo de autenticación completo (End-to-End) operativo entre Frontend y Backend.
- [ ] Esquema relacional base (entidades Usuario y Rol) inicializado en el motor de base de datos.
- [ ] Pipeline CI/CD configurado y ejecutando la fase de build exitosamente ante cada integración en la rama `main`.
- [ ] La iteración concluye con una demostración funcional al Product Owner sin deficiencias críticas o bloqueantes.

---

> 📚 Toda la documentación técnica está en la carpeta [`docs/`](docs/).

## Estabilización de la base

El registro de usuarios requiere ADMIN. Conectar y despegar requiere ADMIN; RTL permite ADMIN y GUARDIA. La clave JWT es obligatoria y el contenedor usa las dependencias de `requirements.txt`. Consulta el [plan por fases y estado de validación](docs/WORK_PLAN.md).

## Misiones dinámicas

Aplicar `alembic upgrade head` antes de iniciar esta versión. Las rutas guardadas se ejecutan con `POST /api/v1/missions/{id}/start` (ADMIN); el progreso se consulta en el detalle de la misión. Usar una única instancia de control con un solo worker. La ejecución por horario es opcional mediante `MISSION_SCHEDULER_ENABLED=true` y está desactivada por defecto. Ver [ejecución, cancelación y recuperación](docs/MISSION_EXECUTION.md).

### Video simulado

Con `VIDEO_ENABLED=true`, el backend genera frames sintéticos y ofrece snapshots
JPEG y streaming MJPEG autenticado. También permite reproducir un archivo local
como fuente simulada. Consulta [activación, endpoints y pruebas de video](docs/VIDEO.md).
