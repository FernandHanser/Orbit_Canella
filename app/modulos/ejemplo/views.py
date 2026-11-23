"""Pantallas del módulo de ejemplo.

No lleva decoradores de seguridad: el núcleo verifica sesión y permiso del módulo
antes de cualquier ruta de este Blueprint (ver app/core/autorizacion.py).
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.core.ejecuciones import EjecucionEnCurso, ejecutar_tarea, ultimas_ejecuciones
from app.core.logs import get_logger

bp = Blueprint("ejemplo", __name__, template_folder="templates")
log = get_logger("ejemplo")


@bp.route("/")
def inicio():
    log.debug("Pantalla principal consultada", extra={"evento": "vista.inicio"})
    ejecuciones = ultimas_ejecuciones("ejemplo", usuario_id=current_user.id, limite=10)
    return render_template("ejemplo/inicio.html", ejecuciones=ejecuciones)


@bp.route("/ejecutar", methods=["POST"])
def ejecutar():
    parametros = {"pasos": request.form.get("pasos", "3"), "fallar": request.form.get("fallar", "")}
    try:
        ejecucion = ejecutar_tarea("ejemplo", "demo", usuario_id=current_user.id, parametros=parametros)
    except EjecucionEnCurso as exc:
        flash(f"{exc} Espera a que termine.", "warning")
        return redirect(url_for("ejemplo.inicio"))
    if ejecucion.estado == "error":
        flash(f"La ejecución {ejecucion.id[:8]} terminó con error: {ejecucion.error}", "danger")
    elif ejecucion.estado == "advertencia":
        flash(f"La ejecución {ejecucion.id[:8]} terminó con advertencias.", "warning")
    else:
        flash(f"Ejecución {ejecucion.id[:8]} completada.", "success")
    return redirect(url_for("ejemplo.inicio"))
