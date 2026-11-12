# Guía de Desarrollo

Esta guía cubre todo lo necesario para configurar el entorno local, correr el servidor, ejecutar los tests y contribuir al proyecto.

---

## Índice

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Variables de Entorno](#variables-de-entorno)
- [Base de Datos](#base-de-datos)
- [Correr el Servidor](#correr-el-servidor)
- [Ejecutar los Tests](#ejecutar-los-tests)
- [Linter y Formato](#linter-y-formato)
- [Migraciones con Alembic](#migraciones-con-alembic)
- [Flujo de trabajo Git](#flujo-de-trabajo-git)
- [CI/CD con GitHub Actions](#cicd-con-github-actions)

---

## Requisitos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | ≥ 3.11 | Se recomienda 3.12+ |
| PostgreSQL | ≥ 15 | Para desarrollo y producción |
| Docker + Compose | Cualquiera | Forma más rápida de levantar la DB |
| Git | Cualquiera | — |

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/AngelCenArr/drones-backend.git
cd drones-backend

# 2. Crear el entorno virtual
python3 -m venv venv

# 3. Activarlo
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 4. Instalar todas las dependencias
pip install -r requirements.txt
```

> **⚠️ Importante:** Siempre activa el venv antes de ejecutar cualquier comando del proyecto. El sistema puede tener otras versiones de Python o paquetes que entren en conflicto.

---

## Variables de Entorno

```bash
# Copiar la plantilla
cp .env.example .env
```

Edita `.env` con tus valores locales:

```ini
# Base de datos PostgreSQL
DATABASE_URL=postgresql://drone_user:drone_password@localhost:5432/drone_db

# Seguridad JWT
SECRET_KEY=cambia-esto-por-una-clave-aleatoria-de-64-caracteres-minimo
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Configuración de la app
PROJECT_NAME=Drones-Autonomos API
API_V1_STR=/api/v1
```

> El `.env` está en `.gitignore`. Nunca lo subas al repositorio — contiene secretos.

### Generar una SECRET_KEY segura

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Base de Datos

### Opción A — Docker (recomendado para desarrollo local)

```bash
# Levantar PostgreSQL en segundo plano
docker-compose up -d

# Verificar que está corriendo
docker-compose ps

# Ver los logs si algo falla
docker-compose logs db
```

Credenciales por defecto (definidas en `docker-compose.yml`):

| Parámetro | Valor |
|---|---|
| Host | `localhost:5432` |
| Usuario | `drone_user` |
| Contraseña | `drone_password` |
| Base de datos | `drone_db` |

### Opción B — PostgreSQL instalado localmente

```bash
# Crear el usuario y la base de datos
sudo -u postgres psql -c "CREATE USER drone_user WITH PASSWORD 'drone_password';"
sudo -u postgres psql -c "CREATE DATABASE drone_db OWNER drone_user;"
```

---

## Correr el Servidor

Asegúrate de haber aplicado las migraciones primero (ver sección [Migraciones](#migraciones-con-alembic)).

```bash
# Activar el venv
source venv/bin/activate

# Servidor con hot-reload (desarrollo)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Servidor sin hot-reload (staging / producción local)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

El servidor queda disponible en:

| URL | Descripción |
|---|---|
| `http://localhost:8000` | Endpoint raíz |
| `http://localhost:8000/docs` | **Swagger UI** — para explorar y probar la API |
| `http://localhost:8000/redoc` | ReDoc — documentación más legible |
| `http://localhost:8000/api/v1/` | Base de la API v1 |

---

## Ejecutar los Tests

Los tests usan **SQLite en memoria** — no necesitan PostgreSQL ni configuración extra.

```bash
# Activar el venv
source venv/bin/activate

# Correr todos los tests
pytest

# Ver output detallado (incluyendo nombre de cada test)
pytest -v

# Correr solo un módulo
pytest tests/test_auth.py
pytest tests/test_missions.py
pytest tests/test_security.py

# Correr una clase específica
pytest tests/test_auth.py::TestLogin
pytest tests/test_missions.py::TestCreateMission

# Correr un test exacto
pytest tests/test_auth.py::TestLogin::test_login_admin_success

# Detener al primer fallo
pytest -x

# Ver los print() dentro de los tests
pytest -s

# Con reporte de cobertura
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
pytest --cov=app --cov-report=html    # Genera htmlcov/index.html
```

### Suite de tests

| Archivo | Tests | Cubre |
|---|---|---|
| `tests/conftest.py` | (fixtures) | DB en memoria, TestClient, roles, usuarios, tokens |
| `tests/test_auth.py` | 15 | Registro, login, perfil `/me`, validaciones, RBAC |
| `tests/test_missions.py` | 24 | CRUD de misiones, filtros, paginación, permisos |
| `tests/test_security.py` | 9 | bcrypt (hash, verify, salt), JWT (subject, exp, firma) |
| `tests/test_access.py` | 19 | Permisos, alturas y bootstrap |
| `tests/test_config.py` | 3 | Clave JWT obligatoria y longitud mínima |
| `tests/test_drone_navigation.py` | 9 | Navegación, tiempos máximos y telemetría |
| `tests/test_mission_execution.py` | 31 | Ejecución, cancelación, horarios, recuperación y permisos |
| `tests/test_migration_execution.py` | 1 | Migración conservando datos existentes |
| **Total** | **111** | |

**Resultado esperado:**
```
==================== 111 passed ====================
```

### Estrategia de testing

- **Aislamiento total**: SQLite en memoria, esquema creado y destruido por cada test.
- **Sin estado compartido**: cada test empieza con una DB limpia con solo los roles seed.
- **Sin dependencias externas**: no requiere PostgreSQL, Redis, ni DroneKit.
- **RBAC cubierto**: cada endpoint privilegiado tiene tests tanto del rol correcto como del incorrecto.

---

## Linter y Formato

El proyecto usa [Ruff](https://docs.astral.sh/ruff/) — linter y formateador ultrarrápido.

```bash
# Verificar errores
ruff check app/

# Verificar también los tests
ruff check app/ tests/

# Corregir errores automáticamente
ruff check app/ --fix

# Aplicar correcciones más agresivas (unsafe)
ruff check app/ --fix --unsafe-fixes

# Formatear el código
ruff format app/

# Verificar formato sin aplicar cambios (útil en CI)
ruff format app/ --check
```

Las reglas están definidas en `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP"]
#         │    │    │    │    │    └─ pyupgrade (modernizar sintaxis)
#         │    │    │    │    └─ bugbear (bugs comunes)
#         │    │    │    └─ isort (orden de imports)
#         │    │    └─ pyflakes (imports no usados)
#         │    └─ warnings PEP8
#         └─ errores PEP8
```

---

## Migraciones con Alembic

```bash
# Aplicar todas las migraciones pendientes (primera vez o al actualizar)
alembic upgrade head

# Ver el estado actual
alembic current

# Ver el historial de migraciones
alembic history --verbose

# Revertir la última migración
alembic downgrade -1

# Revertir todas las migraciones
alembic downgrade base
```

### Crear una nueva migración

Cuando cambias un modelo (`app/models/`), genera la migración automáticamente:

```bash
# Auto-generar (compara modelos vs DB actual)
alembic revision --autogenerate -m "descripcion del cambio"

# Revisar el archivo generado en alembic/versions/ antes de aplicarlo
alembic upgrade head
```

> **⚠️ Siempre revisa el archivo generado** antes de aplicarlo — Alembic a veces no detecta cambios de tipo o constraints correctamente.

---

## Flujo de trabajo Git

```bash
# Crear una rama para tu feature/fix
git checkout -b feature/nombre-del-feature

# Hacer commits descriptivos (usamos Conventional Commits)
git commit -m "feat: agregar endpoint de geofencing"
git commit -m "fix: corregir validación de coordenadas en waypoints"
git commit -m "docs: actualizar guía de simulación SITL"
git commit -m "test: agregar tests de cancelación de misiones"

# Antes de crear un PR, asegúrate de pasar:
ruff check app/         # 0 errores de linting
pytest                  # 111 tests

# Crear PR hacia main
git push origin feature/nombre-del-feature
```

### Convención de commits

| Prefijo | Cuándo usarlo |
|---|---|
| `feat:` | Nuevo endpoint o funcionalidad |
| `fix:` | Corrección de bug |
| `docs:` | Solo documentación |
| `test:` | Agregar o corregir tests |
| `refactor:` | Refactoring sin cambio de comportamiento |
| `chore:` | Limpieza, dependencias, CI |

---

## CI/CD con GitHub Actions

El pipeline (`.github/workflows/ci.yml`) corre automáticamente en cada push a `main` o `develop` y en cada Pull Request.

### Pasos del pipeline

1. **Checkout** del repositorio
2. **Setup Python 3.11** con caché de pip
3. **Instalar dependencias** (`requirements.txt`)
4. **Copiar `.env.example` → `.env`** (para que los tests tengan config)
5. **Ruff lint** — falla si hay errores de estilo
6. **Ruff format check** — falla si el código no está formateado
7. **Pytest** — falla si cualquier test falla

### Ver el estado del CI

Consulta la pestaña **Actions** en GitHub:  
`https://github.com/AngelCenArr/drones-backend/actions`

> Si el CI falla en tu PR, revisa los logs del paso que falló antes de pedir review.

## Inicialización de administradores

`SECRET_KEY` es obligatoria y debe tener al menos 32 caracteres. Genera un valor con `openssl rand -hex 32` y guárdalo en `.env`; la plantilla no contiene una clave.

Después de `alembic upgrade head`, ejecuta `python -m app.bootstrap_admin`. El comando solicita la contraseña sin mostrarla, crea los roles necesarios y rechaza la operación si ya existe un administrador. Ejecuta este paso una sola vez, antes de abrir la API a clientes. Los siguientes usuarios se crean en `/api/v1/auth/register` con el token de un ADMIN.

Las pruebas generan su propia clave y usan SQLite; no necesitan copiar `.env.example`.

## Integración de ingesta con PostgreSQL

La suite usual usa SQLite y omite `test_postgres_ingestion.py` si no está definida
`TEST_POSTGRES_URL`. Para comprobar migraciones reales y deduplicación con cuatro
procesos independientes:

```bash
TEST_POSTGRES_URL=postgresql://test_user:test_password@localhost:5432/drones_test \
  pytest tests/test_postgres_ingestion.py -v
```

Usar una base de pruebas. El usuario necesita permiso para crear esquemas. El test
crea un esquema con nombre aleatorio, aplica `alembic upgrade head`, ingesta ocho
frames desde procesos separados, verifica un evento y ocho detecciones y elimina
su propio esquema al terminar. No opera sobre tablas del esquema público.

El workflow CI incluye un servicio PostgreSQL 16 y ejecuta este caso junto con
la suite. Esta prueba valida persistencia y concurrencia de detecciones; la
integración de vuelos con PostgreSQL + SITL sigue pendiente.
