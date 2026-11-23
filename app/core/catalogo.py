"""Catálogo de módulos: sincroniza el registro en código con la tabla ``modulos`` y
calcula qué módulos puede ver cada usuario."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.core.logs import get_logger
from app.core.models import Modulo, Usuario
from app.core.registro import DefinicionModulo, registro
from app.extensions import db

log = get_logger("core")


@dataclass
class ModuloDisponible:
    definicion: DefinicionModulo
    catalogo: Modulo


def sincronizar_catalogo() -> dict[str, list[str]]:
    """Crea o actualiza en la base de datos los módulos registrados en código.

    Los módulos nuevos quedan activos pero **sin usuarios asignados**. Los que ya no
    existen en código se conservan (con sus permisos) y se marcan como "sin código" en
    la administración.
    """
    creados, actualizados = [], []
    for definicion in registro().todos():
        fila = db.session.get(Modulo, definicion.id)
        if fila is None:
            fila = Modulo(id=definicion.id, activo=True)
            db.session.add(fila)
            creados.append(definicion.id)
        cambios = {
            "nombre": definicion.nombre,
            "descripcion": definicion.descripcion,
            "icono": definicion.icono,
            "permiso": definicion.permiso,
        }
        if any(getattr(fila, k) != v for k, v in cambios.items()):
            for k, v in cambios.items():
                setattr(fila, k, v)
            if definicion.id not in creados:
                actualizados.append(definicion.id)
    try:
        db.session.commit()
    except IntegrityError:
        # Otro proceso sincronizó al mismo tiempo.
        db.session.rollback()
        return {"creados": [], "actualizados": []}
    if creados or actualizados:
        log.info(
            "Catálogo sincronizado",
            extra={"evento": "catalogo.sincronizado", "datos": {"creados": creados, "actualizados": actualizados}},
        )
    return {"creados": creados, "actualizados": actualizados}


def sincronizar_si_hay_esquema(app) -> None:
    """Sincroniza al arrancar solo si las migraciones ya se aplicaron."""
    with app.app_context():
        try:
            if inspect(db.engine).has_table(Modulo.__tablename__):
                sincronizar_catalogo()
        except Exception:
            log.exception("No se pudo sincronizar el catálogo al iniciar", extra={"evento": "catalogo.error"})


def modulos_de_usuario(usuario: Usuario) -> list[ModuloDisponible]:
    """Módulos registrados, habilitados y asignados al usuario."""
    if not usuario.is_authenticated or not usuario.activo:
        return []
    asignados = usuario.modulos_ids()
    if not asignados:
        return []
    # "== True" y no ".is_(True)": en SQL Server "IS 1" no es válido.
    filas = {m.id: m for m in Modulo.query.filter(Modulo.id.in_(asignados), Modulo.activo == True)}  # noqa: E712
    return [
        ModuloDisponible(definicion=d, catalogo=filas[d.id]) for d in registro().todos() if d.id in filas
    ]
