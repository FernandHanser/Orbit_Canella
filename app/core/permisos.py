"""Permisos dentro de un módulo (contrato público del núcleo para los módulos).

El acceso a un módulo lo verifica ``autorizacion`` antes de cualquier ruta. Dentro del módulo,
algunas acciones (por ejemplo, cambiar su configuración) son solo para administradores del hub.
Los módulos usan estas funciones en lugar de leer el rol del usuario o escribir sus propios
decoradores::

    from app.core.permisos import es_administrador, solo_administradores

    @bp.route("/empresas/nueva", methods=["GET", "POST"])
    @solo_administradores
    def empresa_nueva(): ...

    render_template(..., puede_editar=es_administrador())
"""
from __future__ import annotations

from functools import wraps

from flask import request
from flask_login import current_user

from app.core.autorizacion import respuesta_denegada
from app.core.logs import get_logger

log = get_logger("core")


def es_administrador() -> bool:
    """El usuario en sesión es administrador o superadministrador del hub."""
    return bool(current_user.is_authenticated and current_user.es_admin)


def solo_administradores(vista):
    """La ruta del módulo solo la usan administradores del hub (403 para los demás)."""

    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not es_administrador():
            log.warning(
                "Acción de módulo reservada a administradores",
                extra={"evento": "acceso.denegado", "datos": {"ruta": request.path, "metodo": request.method}},
            )
            return respuesta_denegada("Esta acción es exclusiva de administradores del hub.")
        return vista(*args, **kwargs)

    return envoltura
