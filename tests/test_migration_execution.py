import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.parametrize("initial_revision", ["4cd1d3910acb", "6bf21ac304de", "83b88e5fa6f5"])
def test_execution_migration_preserves_existing_missions(tmp_path, initial_revision):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    env = {**os.environ, "DATABASE_URL": url}

    def migrate(direction, revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", direction, revision],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

    migrate("upgrade", initial_revision)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO roles (id, nombre, created_at) VALUES (1, 'ADMIN', CURRENT_TIMESTAMP)")
            )
            connection.execute(
                text(
                    "INSERT INTO usuarios (id, rol_id, nombre, email, password_hash, activo, created_at) "
                    "VALUES (1, 1, 'Admin', 'test@test.com', 'unused', 1, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO misiones (id, creado_por, nombre, estado, created_at) "
                    "VALUES (1, 1, 'Existing mission', 'PROGRAMADA', CURRENT_TIMESTAMP)"
                )
            )
        migrate("upgrade", "head")
        with engine.connect() as connection:
            row = connection.execute(text("SELECT nombre, waypoints_completados, vehiculo_activo FROM misiones")).one()
            assert tuple(row) == ("Existing mission", 0, None)
        assert any(c["column_names"] == ["vehiculo_activo"] for c in inspect(engine).get_unique_constraints("misiones"))
        assert {"eventos", "detecciones"} <= set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [
                "91ea260427ab"
            ]
        migrate("downgrade", "4cd1d3910acb")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT nombre FROM misiones")).scalar() == "Existing mission"
        migrate("upgrade", "head")
    finally:
        engine.dispose()
