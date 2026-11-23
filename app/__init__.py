"""ORBIT Canella — Hub de Automatizaciones de Contabilidad Canella.

Fábrica de la aplicación: configura extensiones, logging central, seguridad,
Blueprints del núcleo y registra los módulos de ``app/modulos``.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from flask import Flask, g, jsonify, render_template, request, url_for
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.config import BASE_DIR, CONFIGS  # carga .env al importarse
from app.extensions import csrf, db, login_manager, migrate

NOMBRE_PRODUCTO = "ORBIT Canella"
SUBTITULO_PRODUCTO = "Hub de Automatizaciones de Contabilidad Canella"


def create_app(ambiente: str | None = None, **overrides) -> Flask:
    ambiente = ambiente or os.getenv("AUTOMATE_ENV", "development")
    if ambiente not in CONFIGS:
        raise RuntimeError(f"AUTOMATE_ENV desconocido: {ambiente!r}. Opciones: {', '.join(CONFIGS)}")

    app = Flask(__name__)
    app.config.from_object(CONFIGS[ambiente])
    app.config.update(overrides)

    from app.core.logs import configurar_logging, get_logger

    configurar_logging(app)
    log = get_logger("core")

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError(
            "DATABASE_URL es obligatoria: la conexión a AUTOMATE_CANELLA en SQL Server. "
            "Defínela en .env (ver scripts/sqlserver/README.md)."
        )

    if not app.config.get("SECRET_KEY"):
        if ambiente == "production":
            raise RuntimeError("SECRET_KEY es obligatoria en producción. Defínela en el entorno o en .env.")
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        log.warning(
            "SECRET_KEY no definida: se generó una temporal (las sesiones se pierden al reiniciar).",
            extra={"evento": "config.secret_key_temporal"},
        )

    from app.core.migraciones import incluir_en_migracion

    db.init_app(app)
    migrate.init_app(app, db, directory=str(BASE_DIR / "migrations"), render_as_batch=True,
                     include_object=incluir_en_migracion)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.session_protection = "strong"

    from app.core import admin, auth, autorizacion, cli, hub, seguridad
    from app.core.catalogo import modulos_de_usuario, sincronizar_si_hay_esquema
    from app.core.ejecuciones import mantenimiento_al_iniciar
    from app.core.registro import cargar_modulos
    from app.integraciones import stod

    app.register_blueprint(auth.bp)
    app.register_blueprint(hub.bp)
    app.register_blueprint(admin.bp)
    autorizacion.instalar(app)
    seguridad.instalar_cabeceras(app)
    cli.instalar(app)
    stod.instalar(app)
    cargar_modulos(app, paquete="app.modulos")
    _instalar_plantillas(app, modulos_de_usuario)
    _instalar_errores(app)

    if app.config.get("AUTO_SINCRONIZAR_MODULOS", not app.config.get("TESTING")):
        sincronizar_si_hay_esquema(app)
    if app.config.get("AUTO_MANTENIMIENTO_EJECUCIONES", not app.config.get("TESTING")):
        mantenimiento_al_iniciar(app)

    log.info(
        "Aplicación iniciada",
        extra={"evento": "app.inicio", "datos": {"ambiente": ambiente, "modulos": [m.id for m in app.extensions["automate_modulos"].todos()]}},
    )
    return app


def _instalar_plantillas(app: Flask, modulos_de_usuario) -> None:
    @app.context_processor
    def _contexto():
        menu = modulos_de_usuario(current_user) if current_user.is_authenticated else []
        return {"NOMBRE_PRODUCTO": NOMBRE_PRODUCTO, "SUBTITULO_PRODUCTO": SUBTITULO_PRODUCTO, "modulos_menu": menu}

    from app.core.paginacion import url_pagina
    from app.core.roles import ROLES, ROLES_ASIGNABLES_WEB

    app.add_template_global(url_pagina)

    from app.core.sesion import restante as tiempo_sesion

    app.add_template_global(tiempo_sesion, "tiempo_sesion")
    app.add_template_global(ROLES, "ROLES")
    app.add_template_global(ROLES_ASIGNABLES_WEB, "ROLES_ASIGNABLES_WEB")

    @app.template_global("estatico")
    def _estatico(filename: str) -> str:
        """url_for('static') con la fecha del archivo: al reemplazarlo, el navegador lo vuelve a descargar."""
        try:
            version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        except OSError:
            version = None
        return url_for("static", filename=filename, v=version)

    @app.template_filter("hace")
    def _hace(valor) -> str:
        """Tiempo transcurrido legible ("hace 4 min") desde una fecha UTC sin zona."""
        if valor is None:
            return "—"
        segundos = (datetime.now(timezone.utc).replace(tzinfo=None) - valor).total_seconds()
        if segundos < 60:
            return "hace un momento"
        if segundos < 3600:
            return f"hace {int(segundos // 60)} min"
        if segundos < 86400:
            return f"hace {int(segundos // 3600)} h"
        dias = int(segundos // 86400)
        return "ayer" if dias == 1 else f"hace {dias} días"

    @app.template_filter("fecha")
    def _fecha(valor, formato="%d/%m/%Y %H:%M"):
        if valor is None:
            return "—"
        return valor.replace(tzinfo=timezone.utc).astimezone().strftime(formato)


def _instalar_errores(app: Flask) -> None:
    from app.core.autorizacion import respuesta_denegada
    from app.core.logs import get_logger
    from app.core.peticiones import es_peticion_api

    log = get_logger("core")

    from flask_login import current_user as usuario_actual
    from flask_wtf.csrf import CSRFError

    from app.core import sesion

    @app.errorhandler(CSRFError)
    def _csrf(e: CSRFError):
        # Sin sesión, el token CSRF falla porque la sesión venció: se explica y se lleva al login,
        # en lugar de un «400 Bad Request» que hace perder el trabajo sin saber por qué.
        if not usuario_actual.is_authenticated:
            log.info("Formulario recibido con la sesión vencida", extra={"evento": "auth.formulario_sesion_vencida",
                                                                          "datos": {"ruta": request.path}})
            return sesion.respuesta_cierre("formulario")
        if es_peticion_api():
            return jsonify(error="csrf", mensaje="El formulario venció. Recarga la página."), 400
        return render_template("errores/generico.html", codigo=400, titulo="El formulario venció",
                               detalle="La página estuvo abierta demasiado tiempo. Recárgala e inténtalo de nuevo."), 400

    @app.errorhandler(403)
    def _prohibido(_e):
        return respuesta_denegada()

    @app.errorhandler(404)
    def _no_encontrado(_e):
        if es_peticion_api():
            return jsonify(error="no_encontrado"), 404
        return render_template("errores/no_encontrado.html"), 404

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        if es_peticion_api():
            return jsonify(error=e.name.lower().replace(" ", "_"), mensaje=e.description), e.code
        return render_template("errores/generico.html", codigo=e.code, titulo=e.name, detalle=e.description), e.code

    @app.errorhandler(Exception)
    def _error(e: Exception):
        db.session.rollback()
        modulo = getattr(g, "modulo_actual", None)
        log.exception(
            "Error no controlado en %s %s", request.method, request.path,
            extra={"evento": "app.error", "modulo": modulo.id if modulo else None},
        )
        if es_peticion_api():
            return jsonify(error="error_interno", mensaje="Ocurrió un error inesperado. Quedó registrado."), 500
        return render_template("errores/generico.html", codigo=500, titulo="Error interno",
                               detalle="Ocurrió un error inesperado. Quedó registrado para su revisión."), 500
