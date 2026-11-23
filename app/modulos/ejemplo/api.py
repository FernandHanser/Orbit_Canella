"""API del módulo de ejemplo (Blueprint anidado → /m/ejemplo/api/...).

Hereda la protección del Blueprint raíz: sin sesión responde 401 y sin permiso 403.
Las peticiones que modifican datos requieren la cabecera X-CSRFToken.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.core.ejecuciones import EjecucionEnCurso, ejecutar_tarea, ultimas_ejecuciones
from app.core.logs import get_logger

from .views import bp as bp_modulo

api_bp = Blueprint("api", __name__, url_prefix="/api")
log = get_logger("ejemplo")


@api_bp.get("/estado")
def estado():
    ultimas = ultimas_ejecuciones("ejemplo", usuario_id=current_user.id, limite=5)
    return jsonify(modulo="ejemplo", usuario=current_user.usuario_stod, ultimas_ejecuciones=[e.a_dict() for e in ultimas])


@api_bp.post("/ejecuciones")
def crear_ejecucion():
    datos = request.get_json(silent=True) or {}
    log.info("Ejecución solicitada por API", extra={"evento": "api.ejecucion_solicitada"})
    try:
        ejecucion = ejecutar_tarea(
            "ejemplo", "demo", usuario_id=current_user.id,
            parametros={"pasos": datos.get("pasos", 3), "fallar": datos.get("fallar", "")},
        )
    except EjecucionEnCurso as exc:
        en_curso = exc.en_curso.a_dict() if exc.en_curso else None
        return jsonify(error="ejecucion_en_curso", mensaje=str(exc), en_curso=en_curso), 409
    return jsonify(ejecucion.a_dict()), 201 if ejecucion.estado != "error" else 500


bp_modulo.register_blueprint(api_bp)
