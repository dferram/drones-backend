# ruff: noqa: E402
"""
conftest.py — Fixtures compartidos para toda la suite de tests.

Estrategia:
- SQLite en memoria con StaticPool (una sola conexión compartida).
- El esquema se crea antes de cada test y se destruye al terminar.
- El TestClient sobreescribe get_db para usar la sesión de test.
"""

import collections
import collections.abc

collections.MutableMapping = collections.abc.MutableMapping  # parche dronekit

import sys
from pathlib import Path
import os
import secrets

# Configuración aislada: las pruebas no dependen de los secretos del .env local.
os.environ["SECRET_KEY"] = secrets.token_hex(32)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MISSION_SCHEDULER_ENABLED"] = "false"
os.environ["VIDEO_ENABLED"] = "false"
os.environ["VISION_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.api import deps
from app.core.security import get_password_hash
from app.db.base_class import Base
from app.main import app
from app.models.alert import Alerta  # noqa: F401  (registra la tabla en Base.metadata)
from app.models.user import Rol, Usuario
from app.services.mission_service import MissionService, get_mission_service

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()

    session.add_all([
        Rol(nombre="ADMIN", descripcion="Administrador del sistema"),
        Rol(nombre="GUARDIA", descripcion="Guardia de seguridad"),
    ])
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    service = MissionService(TestingSessionLocal)
    app.dependency_overrides[get_mission_service] = lambda: service
    app.dependency_overrides[deps.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    service.shutdown()
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db) -> Usuario:
    rol = db.query(Rol).filter(Rol.nombre == "ADMIN").first()
    user = Usuario(
        nombre="Admin Test",
        email="admin@test.com",
        password_hash=get_password_hash("Admin1234!"),
        rol_id=rol.id,
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def guardia_user(db) -> Usuario:
    rol = db.query(Rol).filter(Rol.nombre == "GUARDIA").first()
    user = Usuario(
        nombre="Guardia Test",
        email="guardia@test.com",
        password_hash=get_password_hash("Guardia1234!"),
        rol_id=rol.id,
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_token(client, admin_user) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin1234!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture()
def guardia_token(client, guardia_user) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": guardia_user.email, "password": "Guardia1234!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]