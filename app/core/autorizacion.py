"""Autorización central del hub.

Se instala como ``before_request`` a nivel de aplicación, por lo que se evalúa en
**todas** las peticiones antes que cualquier vista o hook de un Blueprint:

1. Toda ruta exige sesión, salvo las explícitamente públicas (acceso, salud, estáticos). La
   sesión vence por inactividad o jornada (``core/sesion.py``) y se revalida contra STOD
   periódicamente (``auth.revalidar_sesion``).
2. Las rutas del Blueprint ``admin`` exigen rol de administrador; las del catálogo de
   módulos, superadministrador.
3. Las rutas de un módulo registrado (incluidas sus APIs y Blueprints anidados) exigen
   que el módulo esté habilitado en el catálogo y asignado al usuario.

Ocultar un enlace en el menú no autoriza nada: esta verificación ocurre en el servidor
aunque la URL se escriba directamente.
"""
from __future__ import annotations

from flask import Flask, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.core import sesion
from app.core.auth import revalidar_sesion
from app.core.logs import get_logger
from app.core.models import Modulo
from app.core.peticiones import es_peticion_api
from app.core.registro import registro
from app.extensions import db

log = get_logger("core")

ENDPOINTS_PUBLICOS = {"auth.acceso", "hub.salud", "static"}
ENDPOINTS_SUPERADMIN = {"admin.modulos", "admin.modulos_sincronizar", "admin.modulo_estado"}


def respuesta_no_autenticado():
    if es_peticion_api():
        return jsonify(error="no_autenticado", mensaje="Inicia sesión para continuar."), 401
    siguiente = request.full_path.rstrip("?") if request.method == "GET" else None
    return redirect(url_for("auth.acceso", siguiente=siguiente) if siguiente else url_for("auth.acceso"))


def respuesta_denegada(motivo: str = "No tienes permiso para acceder a esta sección."):
    if es_peticion_api():
        return jsonify(error="acceso_denegado", mensaje=motivo), 403
    return render_template("errores/acceso_denegado.html", motivo=motivo), 403


def respuesta_modulo_no_disponible(definicion=None):
    if es_peticion_api():
        return jsonify(error="modulo_no_disponible", mensaje="El módulo no está disponible."), 503
    return render_template("errores/modulo_no_disponible.html", definicion=definicion), 503


def controlar_acceso():
    endpoint = request.endpoint
    if endpoint is None:
        return None  # 404: lo resuelve el manejador de errores
    if endpoint in ENDPOINTS_PUBLICOS:
        return None

    if not current_user.is_authenticated:
        return respuesta_no_autenticado()

    cierre = sesion.verificar() or revalidar_sesion()
    if cierre is not None:
        return cierre

    blueprints = request.blueprints  # del más interno al Blueprint raíz
    raiz = blueprints[-1] if blueprints else None

    if raiz == "admin" and not current_user.es_admin:
        log.warning(
            "Intento de acceso a administración sin rol",
            extra={"evento": "acceso.denegado", "datos": {"ruta": request.path}},
        )
        return respuesta_denegada("Esta sección es exclusiva de administradores.")
    if endpoint in ENDPOINTS_SUPERADMIN and not current_user.es_superadmin:
        log.warning(
            "Intento de acceso a sección de superadministrador",
            extra={"evento": "acceso.denegado", "datos": {"ruta": request.path}},
        )
        return respuesta_denegada("Esta sección es exclusiva del superadministrador.")

    definicion = registro().obtener(raiz)
    if definicion is None:
        return None

    g.modulo_actual = definicion
    fila = db.session.get(Modulo, definicion.id)
    if fila is None or not fila.activo:
        log.warning(
            "Acceso a módulo no disponible",
            extra={"evento": "modulo.no_disponible", "modulo": definicion.id, "datos": {"ruta": request.path}},
        )
        return respuesta_modulo_no_disponible(definicion)

    if not current_user.tiene_acceso(definicion.id):
        log.warning(
            "Acceso denegado a módulo",
            extra={
                "evento": "acceso.denegado",
                "modulo": definicion.id,
                "datos": {"ruta": request.path, "metodo": request.method},
            },
        )
        return respuesta_denegada(f"No tienes acceso asignado al módulo «{definicion.nombre}».")
    return None


def instalar(app: Flask) -> None:
    app.before_request(controlar_acceso)
