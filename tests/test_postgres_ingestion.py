"""Integración opt-in: TEST_POSTGRES_URL; crea y elimina solo un esquema temporal."""

import multiprocessing
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.detections import ingest_detection
from app.models.detection import Deteccion
from app.models.event import Evento
from app.schemas.detection import DeteccionCreate


def ingest_in_process(url):
    engine = create_engine(url)
    try:
        with sessionmaker(bind=engine)() as db:
            detection = ingest_detection(
                DeteccionCreate(
                    tipo="HUMO",
                    nivel_confianza=0.95,
                    latitud=20.58,
                    longitud=-100.38,
                    timestamp="2026-10-20T05:00:00Z",
                ),
                db,
            )
            return detection.evento_id
    finally:
        engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Requiere TEST_POSTGRES_URL")
def test_postgres_migrations_and_concurrent_ingestion():
    base_url = make_url(os.environ["TEST_POSTGRES_URL"])
    schema = "test_ingest_" + uuid4().hex
    admin_engine = create_engine(base_url)
    url = base_url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    engine = create_engine(url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env={**os.environ, "DATABASE_URL": url},
            check=True,
            capture_output=True,
            timeout=60,
        )
        # Cada proceso tiene su propio RLock: la exclusión depende de PostgreSQL.
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as executor:
            ids = list(executor.map(ingest_in_process, [url] * 8))
        assert len(set(ids)) == 1
        with sessionmaker(bind=engine)() as db:
            assert db.query(Deteccion).count() == 8
            assert db.query(Evento).count() == 1
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
