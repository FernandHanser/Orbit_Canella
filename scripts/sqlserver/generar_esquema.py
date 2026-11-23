"""Genera ``02_esquema.sql``: el esquema completo del hub para SQL Server.

Se construye desde los modelos (núcleo y módulos registrados) y deja la base marcada con la
última migración de Alembic, así que después ``flask --app wsgi db upgrade`` solo aplicará las
migraciones nuevas. Volver a ejecutarlo cada vez que se agregue una migración:

    python scripts/sqlserver/generar_esquema.py
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("LOG_CONSOLA", "0")
os.environ.setdefault("LOG_ARCHIVO", "0")

from alembic.config import Config as ConfigAlembic  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy.dialects import mssql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

SALIDA = Path(__file__).with_name("02_esquema.sql")


def _datos_iniciales(scripts: ScriptDirectory, dialecto) -> list[str]:
    """INSERT de los ``DATOS_INICIALES`` (y luego ``SQL_INICIAL``) que declaran las migraciones, en orden.

    Las migraciones siembran sus datos con ``op.bulk_insert(tabla, DATOS_INICIALES[...])``; como
    este script crea las tablas desde los modelos y no aplica migraciones, los toma de ahí."""
    bloques = []
    for revision in reversed(list(scripts.walk_revisions())):
        for nombre_tabla, filas in getattr(revision.module, "DATOS_INICIALES", {}).items():
            tabla = db.metadata.tables[nombre_tabla]
            bloques.append(f"-- Datos iniciales de {nombre_tabla} (migración {revision.revision})")
            for fila in filas:
                sentencia = tabla.insert().values(**fila).inline()  # sin "OUTPUT inserted.id" (ruido en SSMS)
                bloques.append(str(sentencia.compile(dialect=dialecto, compile_kwargs={"literal_binds": True})).strip() + ";")
        # Datos que dependen de otros (p. ej. llaves foráneas por nombre): SQL simple en SQL_INICIAL.
        sentencias = getattr(revision.module, "SQL_INICIAL", [])
        if sentencias:
            bloques.append(f"-- Datos iniciales dependientes (migración {revision.revision})")
            bloques += [s.strip().rstrip(";") + ";" for s in sentencias]
    return bloques


def main() -> None:
    create_app("testing", AUTO_SINCRONIZAR_MODULOS=False)  # registra los modelos de los módulos
    dialecto = mssql.dialect()
    dialecto.deprecate_large_types = True  # Text → VARCHAR(MAX) en lugar del obsoleto TEXT

    alembic = ConfigAlembic()
    alembic.set_main_option("script_location", str(RAIZ / "migrations"))
    cabeza = ScriptDirectory.from_config(alembic).get_current_head()

    scripts = ScriptDirectory.from_config(alembic)
    bloques = []
    for tabla in db.metadata.sorted_tables:
        bloques.append(str(CreateTable(tabla).compile(dialect=dialecto)).strip() + ";")
        for indice in sorted(tabla.indexes, key=lambda i: i.name):
            bloques.append(str(CreateIndex(indice).compile(dialect=dialecto)).strip() + ";")
    bloques += _datos_iniciales(scripts, dialecto)

    contenido = f"""/*
  ORBIT Canella — 2/2: tablas del hub en SQL Server.

  Generado por scripts/sqlserver/generar_esquema.py el {date.today():%d/%m/%Y}
  (migración de Alembic: {cabeza}). No editar a mano: regenerarlo.

  Ejecutar después de 01_crear_base.sql. Crea todas las tablas en una transacción: si algo
  falla, no queda nada a medias.
*/
USE [AUTOMATE_CANELLA];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
-- Requeridos por el índice filtrado de HUB_EJECUCIONES (sqlcmd trae QUOTED_IDENTIFIER en OFF).
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
BEGIN TRANSACTION;

{chr(10).join(bloques)}

-- Versión del esquema para Alembic: las próximas migraciones parten de aquí.
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('{cabeza}');

COMMIT TRANSACTION;
PRINT N'Esquema de ORBIT Canella creado (migración {cabeza}).';
GO
"""
    SALIDA.write_text(contenido, encoding="utf-8-sig")  # con BOM: sqlcmd y SSMS leen bien las tildes
    print(f"Generado {SALIDA.relative_to(RAIZ)} ({len(db.metadata.sorted_tables)} tablas, migración {cabeza})")


if __name__ == "__main__":
    main()
