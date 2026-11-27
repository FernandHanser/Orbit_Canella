"""Migraciones de Alembic.

* Autogenerate nunca propone borrar tablas de un módulo que no está cargado.
* La cadena de ``migrations/versions/`` se puede aplicar de verdad: el resto de las pruebas crea
  las tablas con ``db.create_all()`` desde los modelos, así que sin estas pruebas una migración
  rota o que no coincide con los modelos solo se descubriría al desplegar (``actualizar.ps1``
  aplica ``flask db upgrade`` en el servidor de pruebas en cada push a ``dev``).

Límite: corren sobre SQLite. Lo que solo falla en SQL Server (índices filtrados, ``ALTER COLUMN``,
nombres de restricciones) o lo que depende de los datos ya cargados no se detecta aquí.
"""
import logging
from contextlib import contextmanager

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from app import create_app
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


# ---------------------------------------------------------------------------- la cadena real

@contextmanager
def _conservar_logging():
    """``migrations/env.py`` llama a ``logging.config.fileConfig``, que deshabilita los loggers
    existentes y cambia la raíz. Se restaura todo para no afectar a las pruebas que siguen."""
    raiz = logging.getLogger()
    nivel, manejadores = raiz.level, list(raiz.handlers)
    loggers = {n: (l.disabled, l.level, list(l.handlers), l.propagate)
               for n, l in logging.Logger.manager.loggerDict.items() if isinstance(l, logging.Logger)}
    try:
        yield
    finally:
        raiz.setLevel(nivel)
        raiz.handlers[:] = manejadores
        for nombre, (deshabilitado, nivel_l, manejadores_l, propaga) in loggers.items():
            l = logging.getLogger(nombre)
            l.disabled, l.propagate = deshabilitado, propaga
            l.setLevel(nivel_l)
            l.handlers[:] = manejadores_l


@pytest.fixture
def app_vacia(tmp_path):
    """Hub sobre un SQLite en archivo **sin** tablas: las crean solo las migraciones."""
    ruta = (tmp_path / "migraciones.db").as_posix()
    app = create_app("testing", LOG_DIR=str(tmp_path / "logs"), SQLALCHEMY_DATABASE_URI=f"sqlite:///{ruta}")
    with app.app_context(), _conservar_logging():
        yield app
        db.session.remove()
        db.engine.dispose()


def _tablas():
    return set(inspect(db.engine).get_table_names()) - {"alembic_version"}


def test_la_cadena_tiene_una_sola_cabeza(app_vacia):
    # Dos ramas que generan migraciones a la vez dejan dos «heads» y `db upgrade` se niega a correr.
    # Se unen con `flask --app wsgi db merge heads` (docs/AGREGAR_MODULO.md).
    cabezas = ScriptDirectory.from_config(app_vacia.extensions["migrate"].migrate.get_config()).get_heads()
    assert len(cabezas) == 1, f"La cadena de migraciones tiene varias cabezas: {cabezas}"


def test_upgrade_desde_cero_deja_el_mismo_esquema_que_los_modelos(app_vacia):
    upgrade()
    with db.engine.connect() as conexion:
        contexto = MigrationContext.configure(
            conexion, opts={"include_object": incluir_en_migracion, "compare_type": True})
        diferencias = compare_metadata(contexto, db.metadata)
    # Si falla: falta una migración (`flask --app wsgi db migrate`) o la que hay no coincide con
    # los modelos. Cada elemento dice qué tabla o columna difiere.
    assert diferencias == []
    assert _tablas() == set(db.metadata.tables)


def test_corte_caja_queda_con_la_estructura_oficial_de_carpetas(app_vacia):
    # 5869c708f797: nombres y subcarpetas que usa Contabilidad en producción (prototipo, 083118e).
    upgrade()
    with db.engine.connect() as conexion:
        filas = dict(conexion.execute(text('SELECT carpeta, plantilla_carpeta FROM "CORTE_CAJA_EMPRESAS"')).all())
    assert filas == {
        "Maquipos": "1.Año {AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}",
        "Vesa": "1.Año {AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}",
        "Cobradores": "1.Año {AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}",
        "Mister Credit": "1.Año {AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}",
        "Mauto": "1.Año{AAAA}/{MM} {MES} {AAAA}/{DD}-{MM}-{AA}",
        "Canella": "1.Año{AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}",
    }
    downgrade(revision="5e2b9c4d7a10")
    with db.engine.connect() as conexion:
        nombres = {c for (c,) in conexion.execute(text('SELECT carpeta FROM "CORTE_CAJA_EMPRESAS"'))}
    assert nombres == {"MAQUIPOS", "VESA", "Cobradores", "Mauto", "MR. Credit", "CANELLA"}


def test_downgrade_deshace_todo_y_se_puede_volver_a_aplicar(app_vacia):
    # El plan de reversa de docs/DESPLIEGUE.md es `db downgrade`: tiene que funcionar.
    upgrade()
    downgrade(revision="base")
    assert _tablas() == set(), "downgrade dejó tablas sin borrar"
    upgrade()
    assert _tablas() == set(db.metadata.tables)
