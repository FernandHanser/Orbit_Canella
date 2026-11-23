"""Autogenerate nunca propone borrar tablas de un módulo que no está cargado."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.core.migraciones import incluir_en_migracion
from app.extensions import db


def _diferencias(conexion, filtro=None):
    opciones = {"include_object": filtro} if filtro else {}
    return compare_metadata(MigrationContext.configure(conexion, opts=opciones), db.metadata)


def test_ignora_tablas_de_modulos_no_cargados(app):
    with db.engine.begin() as conexion:
        conexion.execute(text("CREATE TABLE OTRO_MODULO_DATOS (id INTEGER PRIMARY KEY)"))
        # Sin el filtro, Alembic propondría borrarla: es el riesgo que se cubre.
        assert any(d[0] == "remove_table" for d in _diferencias(conexion))
        assert not any(d[0] == "remove_table" for d in _diferencias(conexion, incluir_en_migracion))


def test_sigue_detectando_tablas_nuevas_de_los_modulos_cargados(app):
    with db.engine.begin() as conexion:
        conexion.execute(text('DROP TABLE "CORTE_CAJA_ARCHIVOS"'))
        nuevas = [d[1].name for d in _diferencias(conexion, incluir_en_migracion) if d[0] == "add_table"]
    assert nuevas == ["CORTE_CAJA_ARCHIVOS"]


def test_el_hub_usa_el_filtro(app):
    assert app.extensions["migrate"].configure_args["include_object"] is incluir_en_migracion
