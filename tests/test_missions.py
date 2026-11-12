from fastapi import status


# 1. Verificar bloqueo por falta de autenticación (401 Unauthorized)
def test_create_mission_without_token(client):
    payload = {
        "nombre": "Ruta No Autorizada",
        "descripcion": "Intento sin token",
        "waypoints": [
            {"orden_waypoint": 1, "latitud": 20.588, "longitud": -100.389, "altitud_metros": 15.0},
            {"orden_waypoint": 2, "latitud": 20.589, "longitud": -100.390, "altitud_metros": 15.0},
        ],
    }
    response = client.post("/api/v1/missions/", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# 2. Verificar bloqueo de GUARDIA al intentar crear misiones (403 Forbidden)
def test_guardia_cannot_create_mission(client, guardia_token):
    headers = {"Authorization": f"Bearer {guardia_token}"}
    payload = {
        "nombre": "Misión Intrusión",
        "descripcion": "Creada por guardia (no permitido)",
        "waypoints": [
            {"orden_waypoint": 1, "latitud": 20.588, "longitud": -100.389, "altitud_metros": 15.0},
            {"orden_waypoint": 2, "latitud": 20.589, "longitud": -100.390, "altitud_metros": 15.0},
        ],
    }
    response = client.post("/api/v1/missions/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Operación no permitida para el rol asignado."


# 3. Verificar que ADMIN sí puede crear misiones (201 Created)
def test_admin_can_create_mission(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "nombre": "Patrullaje Nocturno Aulas",
        "descripcion": "Vigilancia de pasillos exteriores",
        "waypoints": [
            {"orden_waypoint": 1, "latitud": 20.5881, "longitud": -100.3891, "altitud_metros": 15.0},
            {"orden_waypoint": 2, "latitud": 20.5892, "longitud": -100.3902, "altitud_metros": 18.0},
        ],
    }
    response = client.post("/api/v1/missions/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["nombre"] == "Patrullaje Nocturno Aulas"
    assert data["estado"] == "PROGRAMADA"
    assert len(data["waypoints"]) == 2


# 4. Verificar que tanto GUARDIA como ADMIN pueden listar misiones
def test_guardia_can_list_missions(client, guardia_token):
    headers = {"Authorization": f"Bearer {guardia_token}"}
    response = client.get("/api/v1/missions/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


# 5. Verificar cancelación de misión (Guardia o Admin)
def test_cancel_mission(client, admin_token, guardia_token):
    # Crear como Admin
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "nombre": "Misión para Cancelar",
        "waypoints": [
            {"orden_waypoint": 1, "latitud": 20.588, "longitud": -100.389, "altitud_metros": 15.0},
            {"orden_waypoint": 2, "latitud": 20.589, "longitud": -100.390, "altitud_metros": 15.0},
        ],
    }
    mision_res = client.post("/api/v1/missions/", json=payload, headers=headers_admin).json()
    mision_id = mision_res["id"]

    # Cancelar con token de Guardia
    headers_guardia = {"Authorization": f"Bearer {guardia_token}"}
    cancel_res = client.post(f"/api/v1/missions/{mision_id}/cancel", headers=headers_guardia)
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["estado"] == "CANCELADA"


"""
test_missions.py — Tests del CRUD de misiones.

Cubre:
- POST /api/v1/missions/        → crear misión (admin), sin auth, guardia sin permiso
- GET  /api/v1/missions/        → listar misiones, filtro por estado, paginación
- GET  /api/v1/missions/{id}    → obtener misión por ID, ID inexistente
- PUT  /api/v1/missions/{id}    → editar misión PROGRAMADA, editar EN_CURSO (error)
- POST /api/v1/missions/{id}/cancel → cancelar misión, cancelar CANCELADA (error)
"""

# ---------------------------------------------------------------------------
# Payload de misión válida con 2 waypoints mínimos
# ---------------------------------------------------------------------------
MISION_PAYLOAD = {
    "nombre": "Patrulla Nocturna A",
    "descripcion": "Recorrido perimetral sector norte",
    "horario_inicio_programado": "2026-10-01T22:00:00",
    "waypoints": [
        {"orden_waypoint": 1, "latitud": 20.704, "longitud": -100.443, "altitud_metros": 20.0},
        {"orden_waypoint": 2, "latitud": 20.705, "longitud": -100.442, "altitud_metros": 20.0},
    ],
}


# =============================================================================
# CREAR MISIÓN  (POST /)
# =============================================================================


class TestCreateMission:
    ENDPOINT = "/api/v1/missions/"

    def test_admin_creates_mission(self, client, admin_token):
        """ADMIN puede crear una misión con waypoints."""
        r = client.post(
            self.ENDPOINT,
            json=MISION_PAYLOAD,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["nombre"] == MISION_PAYLOAD["nombre"]
        assert data["estado"] == "PROGRAMADA"
        assert len(data["waypoints"]) == 2
        assert data["waypoints"][0]["orden_waypoint"] == 1

    def test_create_mission_without_auth(self, client):
        """Sin token devuelve 401."""
        r = client.post(self.ENDPOINT, json=MISION_PAYLOAD)
        assert r.status_code == 401

    def test_guardia_cannot_create_mission(self, client, guardia_token):
        """GUARDIA no puede crear misiones → 403."""
        r = client.post(
            self.ENDPOINT,
            json=MISION_PAYLOAD,
            headers={"Authorization": f"Bearer {guardia_token}"},
        )
        assert r.status_code == 403

    def test_create_mission_insufficient_waypoints(self, client, admin_token):
        """Misión con solo 1 waypoint devuelve 422 (mínimo 2)."""
        payload = {**MISION_PAYLOAD, "waypoints": [MISION_PAYLOAD["waypoints"][0]]}
        r = client.post(
            self.ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_create_mission_empty_nombre(self, client, admin_token):
        """Nombre vacío devuelve 422."""
        payload = {**MISION_PAYLOAD, "nombre": "ab"}  # min_length=3
        r = client.post(
            self.ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422

    def test_create_mission_invalid_coords(self, client, admin_token):
        """Coordenadas fuera de rango devuelven 422."""
        payload = {
            **MISION_PAYLOAD,
            "waypoints": [
                {"orden_waypoint": 1, "latitud": 200.0, "longitud": -100.443, "altitud_metros": 20.0},
                {"orden_waypoint": 2, "latitud": 20.705, "longitud": -100.442, "altitud_metros": 20.0},
            ],
        }
        r = client.post(
            self.ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422


# =============================================================================
# LISTAR MISIONES  (GET /)
# =============================================================================


class TestListMissions:
    ENDPOINT = "/api/v1/missions/"

    def _create(self, client, token, nombre="Misión Test"):
        payload = {**MISION_PAYLOAD, "nombre": nombre}
        r = client.post(self.ENDPOINT, json=payload, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        return r.json()

    def test_admin_lists_missions(self, client, admin_token):
        """ADMIN puede listar misiones."""
        self._create(client, admin_token)
        r = client.get(self.ENDPOINT, headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_guardia_lists_missions(self, client, admin_token, guardia_token):
        """GUARDIA también puede listar misiones."""
        self._create(client, admin_token)
        r = client.get(self.ENDPOINT, headers={"Authorization": f"Bearer {guardia_token}"})
        assert r.status_code == 200

    def test_list_missions_without_auth(self, client):
        """Sin token devuelve 401."""
        r = client.get(self.ENDPOINT)
        assert r.status_code == 401

    def test_list_missions_filter_by_estado(self, client, admin_token):
        """Filtrar por estado=PROGRAMADA devuelve solo misiones programadas."""
        self._create(client, admin_token, "Misión Filtro")
        r = client.get(
            self.ENDPOINT,
            params={"estado": "PROGRAMADA"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        misiones = r.json()
        assert all(m["estado"] == "PROGRAMADA" for m in misiones)

    def test_list_missions_empty_filter(self, client, admin_token):
        """Filtrar por estado inexistente devuelve lista vacía."""
        self._create(client, admin_token)
        r = client.get(
            self.ENDPOINT,
            params={"estado": "ESTADO_INVALIDO"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_list_missions_pagination(self, client, admin_token):
        """Paginación con skip/limit funciona correctamente."""
        for i in range(3):
            self._create(client, admin_token, f"Misión Pag {i}")

        r = client.get(
            self.ENDPOINT,
            params={"skip": 0, "limit": 2},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert len(r.json()) <= 2


# =============================================================================
# OBTENER MISIÓN POR ID  (GET /{id})
# =============================================================================


class TestGetMission:
    def _create(self, client, token):
        r = client.post(
            "/api/v1/missions/",
            json=MISION_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        return r.json()

    def test_get_existing_mission(self, client, admin_token, guardia_token):
        """Obtener una misión existente devuelve sus datos completos."""
        mision = self._create(client, admin_token)
        r = client.get(
            f"/api/v1/missions/{mision['id']}",
            headers={"Authorization": f"Bearer {guardia_token}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == mision["id"]
        assert len(r.json()["waypoints"]) == 2

    def test_get_nonexistent_mission(self, client, admin_token):
        """ID inexistente devuelve 404."""
        r = client.get(
            "/api/v1/missions/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    def test_get_mission_without_auth(self, client):
        """Sin token devuelve 401."""
        r = client.get("/api/v1/missions/1")
        assert r.status_code == 401


# =============================================================================
# EDITAR MISIÓN  (PUT /{id})
# =============================================================================


class TestUpdateMission:
    def _create(self, client, token):
        r = client.post(
            "/api/v1/missions/",
            json=MISION_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        return r.json()

    def test_admin_updates_programmed_mission(self, client, admin_token):
        """ADMIN puede editar una misión en estado PROGRAMADA."""
        mision = self._create(client, admin_token)
        r = client.put(
            f"/api/v1/missions/{mision['id']}",
            json={"nombre": "Patrulla Actualizada", "descripcion": "Nueva descripción"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["nombre"] == "Patrulla Actualizada"
        assert r.json()["descripcion"] == "Nueva descripción"

    def test_guardia_cannot_update_mission(self, client, admin_token, guardia_token):
        """GUARDIA no puede editar misiones → 403."""
        mision = self._create(client, admin_token)
        r = client.put(
            f"/api/v1/missions/{mision['id']}",
            json={"nombre": "Intento Guardia"},
            headers={"Authorization": f"Bearer {guardia_token}"},
        )
        assert r.status_code == 403

    def test_update_nonexistent_mission(self, client, admin_token):
        """Editar un ID inexistente devuelve 404."""
        r = client.put(
            "/api/v1/missions/99999",
            json={"nombre": "No existe"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    def test_update_cancelled_mission_fails(self, client, admin_token):
        """No se puede editar una misión CANCELADA → 400."""
        mision = self._create(client, admin_token)
        # Cancelar primero
        client.post(
            f"/api/v1/missions/{mision['id']}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Intentar editar
        r = client.put(
            f"/api/v1/missions/{mision['id']}",
            json={"nombre": "Editando cancelada"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400


# =============================================================================
# CANCELAR MISIÓN  (POST /{id}/cancel)
# =============================================================================


class TestCancelMission:
    def _create(self, client, token):
        r = client.post(
            "/api/v1/missions/",
            json=MISION_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        return r.json()

    def test_admin_cancels_mission(self, client, admin_token):
        """ADMIN puede cancelar una misión PROGRAMADA."""
        mision = self._create(client, admin_token)
        r = client.post(
            f"/api/v1/missions/{mision['id']}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["estado"] == "CANCELADA"

    def test_guardia_cancels_mission(self, client, admin_token, guardia_token):
        """GUARDIA también puede cancelar misiones."""
        mision = self._create(client, admin_token)
        r = client.post(
            f"/api/v1/missions/{mision['id']}/cancel",
            headers={"Authorization": f"Bearer {guardia_token}"},
        )
        assert r.status_code == 200
        assert r.json()["estado"] == "CANCELADA"

    def test_cancel_already_cancelled_mission(self, client, admin_token):
        """Cancelar una misión ya CANCELADA devuelve 400."""
        mision = self._create(client, admin_token)
        # Primera cancelación → OK
        client.post(
            f"/api/v1/missions/{mision['id']}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Segunda cancelación → error
        r = client.post(
            f"/api/v1/missions/{mision['id']}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400

    def test_cancel_nonexistent_mission(self, client, admin_token):
        """Cancelar un ID inexistente devuelve 404."""
        r = client.post(
            "/api/v1/missions/99999/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    def test_cancel_without_auth(self, client, admin_token):
        """Sin token devuelve 401."""
        mision = self._create(client, admin_token)
        r = client.post(f"/api/v1/missions/{mision['id']}/cancel")
        assert r.status_code == 401
