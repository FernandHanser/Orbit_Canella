"""Filtro de Alembic para un monolito modular con una sola cadena de migraciones.

Autogenerate compara la base con los modelos *cargados*. Si un módulo no se cargó (lista
``AUTOMATE_MODULOS`` limitada, carpeta retirada o módulo que falló al importarse), sus tablas
existen en la base pero no en los modelos, y ``flask db migrate`` propondría borrarlas con todos
sus datos. Este filtro hace que Alembic ignore toda tabla que no conoce: nunca propone un
``DROP TABLE``.

Costo aceptado: retirar una tabla a propósito se escribe a mano en la migración
(``op.drop_table``). Ver docs/AGREGAR_MODULO.md#retirar-un-módulo-con-tablas.
"""
from __future__ import annotations


def incluir_en_migracion(objeto, nombre, tipo, reflejado, comparar_con) -> bool:
    """``include_object`` de Alembic: deja fuera las tablas que están en la base y no en los modelos."""
    if tipo == "table" and reflejado and comparar_con is None:
        return False
    return True
