"""Expiración de la sesión: inactividad y jornada máxima, con el motivo para el usuario.

El servidor decide; el navegador solo avisa (``static/js/sesion.js``):

* **Inactividad** (``SESION_INACTIVIDAD_MINUTOS``, 60): sin peticiones durante ese tiempo, la
  sesión se cierra. Cada petición la renueva, salvo la consulta de estado del aviso.
* **Jornada** (``SESION_MAXIMA_HORAS``, 10): tope desde el inicio de sesión aunque haya actividad;
  obliga a volver a validar con STOD.
* La cookie vive lo que la jornada (``PERMANENT_SESSION_LIFETIME``): así el servidor todavía la
  recibe al vencer la inactividad y puede decir **por qué** se cerró (``?motivo=`` en el login).

Motivos: ``inactividad``, ``jornada``, ``stod`` (ya no activo en STOD) y ``formulario`` (se envió
un formulario después de vencer la sesión; ver el manejador de CSRF en ``app/__init__.py``).
"""
from __future__ import annotations

import time

from flask import current_app, jsonify, redirect, request, session, url_for
from flask_login import logout_user

from app.core.logs import get_logger
from app.core.peticiones import es_peticion_api

log = get_logger("core")

CLAVE_INICIO = "sesion_inicio"
CLAVE_ULTIMA = "sesion_ultima"
# Consultar cuánto falta no cuenta como actividad (si no, el aviso mantendría viva la sesión).
ENDPOINTS_SIN_ACTIVIDAD = {"auth.sesion_estado"}

MOTIVOS = {
    "inactividad": "Tu sesión se cerró por inactividad, por seguridad. Vuelve a entrar para continuar donde estabas.",
    "jornada": "Tu sesión llegó a su duración máxima y se cerró por seguridad. Vuelve a entrar para continuar.",
    "stod": "Tu usuario ya no está activo en STOD, por eso se cerró la sesión. Contacta a la mesa de ayuda Canella.",
    "formulario": "Tu sesión había vencido cuando enviaste el formulario, así que no se guardó. Vuelve a entrar e inténtalo de nuevo.",
}


def inactividad_s() -> int:
    return int(current_app.config["SESION_INACTIVIDAD_MINUTOS"] * 60)


def maxima_s() -> int:
    return int(current_app.config["SESION_MAXIMA_HORAS"] * 3600)


def iniciar() -> None:
    """Al iniciar sesión: marca el inicio de la jornada y la última actividad."""
    ahora = int(time.time())
    session[CLAVE_INICIO] = ahora
    session[CLAVE_ULTIMA] = ahora


def restante() -> dict:
    """Segundos que faltan para cada vencimiento (para el aviso del navegador)."""
    ahora = time.time()
    inicio = session.get(CLAVE_INICIO, ahora)
    ultima = session.get(CLAVE_ULTIMA, ahora)
    por_inactividad = max(0, int(ultima + inactividad_s() - ahora))
    por_jornada = max(0, int(inicio + maxima_s() - ahora))
    return {
        "segundos": min(por_inactividad, por_jornada),
        "motivo": "jornada" if por_jornada <= por_inactividad else "inactividad",
        "inactividad": por_inactividad,
        "jornada": por_jornada,
    }


def respuesta_cierre(motivo: str):
    """Cierra la sesión y lleva al login con el motivo (o 401 en la API)."""
    siguiente = request.full_path.rstrip("?") if request.method == "GET" and not es_peticion_api() else None
    logout_user()
    session.clear()
    if es_peticion_api():
        return jsonify(error="sesion_vencida", motivo=motivo, mensaje=MOTIVOS.get(motivo, "")), 401
    parametros = {"motivo": motivo}
    if siguiente:
        parametros["siguiente"] = siguiente
    return redirect(url_for("auth.acceso", **parametros))


def verificar():
    """Llamada en cada petición con sesión. Devuelve la respuesta de cierre o None."""
    ahora = time.time()
    if CLAVE_INICIO not in session:            # sesiones abiertas antes de este control
        iniciar()
        return None
    vencida = None
    if ahora - session[CLAVE_INICIO] > maxima_s():
        vencida = "jornada"
    elif ahora - session.get(CLAVE_ULTIMA, ahora) > inactividad_s():
        vencida = "inactividad"
    if vencida:
        log.info("Sesión cerrada por %s", vencida, extra={"evento": f"auth.sesion_{vencida}"})
        return respuesta_cierre(vencida)
    if request.endpoint not in ENDPOINTS_SIN_ACTIVIDAD:
        session[CLAVE_ULTIMA] = int(ahora)
    return None
