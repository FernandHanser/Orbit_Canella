"""Inicio y cierre de sesión con usuarios de STOD.

* Entra cualquier usuario **activo en STOD** con su usuario y contraseña de STOD.
* El hub no guarda contraseñas. En el primer ingreso crea el usuario local (rol "usuario",
  sin módulos) y en cada ingreso actualiza su correo y nombre desde STOD.
* Un usuario deshabilitado en el hub no entra aunque esté activo en STOD.
* Cada ``STOD_REVALIDAR_MINUTOS`` se vuelve a comprobar en STOD que siga activo.
* La sesión vence por inactividad o por jornada máxima (``app/core/sesion.py``); el login muestra
  el motivo (``?motivo=``) y vuelve a la página donde estaba (``?siguiente=``).
* El bloqueo por intentos fallidos lo lleva el hub (tabla ``intentos_acceso``); no se escribe
  en STOD.
"""
from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app.core.formularios import FormAcceso
from app.core.identidad import Identidad, IdentidadNoDisponible, normalizar_usuario, proveedor_identidad
from app.core.logs import get_logger
from app.core.models import IntentoAcceso, Usuario, ahora_utc
from app.core.peticiones import es_url_segura
from app.core import sesion
from app.extensions import db, login_manager

bp = Blueprint("auth", __name__)
log = get_logger("core")

MENSAJE_GENERICO = "Usuario o contraseña incorrectos."
MENSAJE_STOD_CAIDO = "No se pudo validar tu usuario con STOD. Intenta de nuevo en unos minutos."
MENSAJE_BLOQUEO = "Demasiados intentos fallidos. Espera {minutos} minutos e intenta de nuevo."
MENSAJE_INACTIVO_STOD = "Tu usuario está inactivo o bloqueado en STOD. Contacta a la mesa de ayuda Canella."
MENSAJE_DESHABILITADO = "Tu acceso a ORBIT Canella está deshabilitado. Contacta a la mesa de ayuda Canella."
FACTOR_LIMITE_IP = 4  # una IP puede fallar hasta LOGIN_MAX_INTENTOS × 4 veces en la ventana


@login_manager.user_loader
def cargar_usuario(identificador: str):
    try:
        usuario_id, version = identificador.split(":", 1)
        usuario = db.session.get(Usuario, int(usuario_id))
    except (ValueError, TypeError):
        return None
    if usuario is None or not usuario.activo or str(usuario.version_sesion) != version:
        return None
    return usuario


# ---------------------------------------------------------------------------- intentos fallidos

def _ip() -> str:
    return (request.remote_addr or "")[:64]


def _bloqueado(usuario: str) -> bool:
    cfg = current_app.config
    desde = ahora_utc() - timedelta(minutes=cfg["LOGIN_BLOQUEO_MINUTOS"])
    por_usuario = IntentoAcceso.query.filter(IntentoAcceso.usuario == usuario, IntentoAcceso.creado_en >= desde).count()
    por_ip = IntentoAcceso.query.filter(IntentoAcceso.ip == _ip(), IntentoAcceso.creado_en >= desde).count()
    return por_usuario >= cfg["LOGIN_MAX_INTENTOS"] or por_ip >= cfg["LOGIN_MAX_INTENTOS"] * FACTOR_LIMITE_IP


def _registrar_fallo(usuario: str, motivo: str) -> None:
    db.session.add(IntentoAcceso(usuario=usuario, ip=_ip()))
    # Limpieza: los intentos de más de un día ya no cuentan.
    IntentoAcceso.query.filter(IntentoAcceso.creado_en < ahora_utc() - timedelta(days=1)).delete()
    db.session.commit()
    log.warning("Inicio de sesión fallido", extra={"evento": "auth.fallido", "datos": {"usuario_stod": usuario, "motivo": motivo}})


# ---------------------------------------------------------------------------- usuario local

def sincronizar_usuario(identidad: Identidad) -> Usuario:
    """Crea el usuario local en su primer ingreso o actualiza sus datos desde STOD."""
    clave = normalizar_usuario(identidad.usuario)
    usuario = Usuario.query.filter_by(usuario_stod=clave).first()
    if usuario is None:
        usuario = Usuario(usuario_stod=clave, rol=Usuario.ROL_USUARIO, activo=True)
        db.session.add(usuario)
        log.info("Usuario registrado en su primer ingreso", extra={"evento": "auth.primer_ingreso", "datos": {"usuario_stod": clave}})
    usuario.stod_user_id = identidad.user_id
    usuario.email = identidad.email
    usuario.nombre = identidad.nombre_visible
    usuario.stod_verificado_en = ahora_utc()
    return usuario


# ---------------------------------------------------------------------------- vistas

@bp.route("/acceso", methods=["GET", "POST"])
def acceso():
    if current_user.is_authenticated:
        return redirect(url_for("hub.inicio"))

    form = FormAcceso()
    siguiente = request.args.get("siguiente")
    aviso = sesion.MOTIVOS.get(request.args.get("motivo", ""))
    if form.validate_on_submit():
        clave = normalizar_usuario(form.usuario.data)
        minutos = current_app.config["LOGIN_BLOQUEO_MINUTOS"]
        if _bloqueado(clave):
            log.warning("Inicio de sesión rechazado por bloqueo temporal", extra={"evento": "auth.bloqueado", "datos": {"usuario_stod": clave}})
            flash(MENSAJE_BLOQUEO.format(minutos=minutos), "danger")
            return render_template("auth/acceso.html", form=form, siguiente=siguiente, aviso=aviso)

        try:
            identidad = proveedor_identidad().autenticar(clave, form.contrasena.data)
        except IdentidadNoDisponible as exc:
            log.error("STOD no disponible al iniciar sesión: %s", exc, extra={"evento": "auth.stod_no_disponible", "datos": {"usuario_stod": clave}})
            flash(MENSAJE_STOD_CAIDO, "danger")
            return render_template("auth/acceso.html", form=form, siguiente=siguiente, aviso=aviso)

        if identidad is None:
            _registrar_fallo(clave, "credenciales")
            flash(MENSAJE_GENERICO, "danger")
        elif not identidad.activo:
            _registrar_fallo(clave, "inactivo_en_stod")
            flash(MENSAJE_INACTIVO_STOD, "danger")
        else:
            usuario = sincronizar_usuario(identidad)
            if not usuario.activo:
                db.session.commit()
                log.warning("Inicio de sesión rechazado: deshabilitado en el hub", extra={"evento": "auth.deshabilitado", "datos": {"usuario_stod": clave}})
                flash(MENSAJE_DESHABILITADO, "danger")
            else:
                usuario.ultimo_acceso = ahora_utc()
                IntentoAcceso.query.filter_by(usuario=clave).delete()
                db.session.commit()
                session.clear()
                login_user(usuario)
                session.permanent = True
                sesion.iniciar()
                log.info("Inicio de sesión", extra={"evento": "auth.acceso", "usuario": usuario.usuario_stod})
                return redirect(siguiente if es_url_segura(siguiente) else url_for("hub.inicio"))

    return render_template("auth/acceso.html", form=form, siguiente=siguiente, aviso=aviso)


@bp.route("/sesion/estado")
def sesion_estado():
    """Cuánto falta para que venza la sesión. No cuenta como actividad (ver core/sesion.py)."""
    return jsonify(sesion.restante())


@bp.route("/sesion/extender", methods=["POST"])
def sesion_extender():
    """«Extender sesión» del aviso: la petición misma renueva la inactividad. La jornada no se extiende."""
    log.info("Sesión extendida desde el aviso", extra={"evento": "auth.sesion_extendida"})
    return jsonify(sesion.restante())


@bp.route("/salir", methods=["POST"])
def salir():
    if current_user.is_authenticated:
        log.info("Cierre de sesión", extra={"evento": "auth.salida"})
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("auth.acceso"))


# ---------------------------------------------------------------------------- revalidación

def revalidar_sesion():
    """Comprueba en STOD, cada ``STOD_REVALIDAR_MINUTOS``, que el usuario siga activo.

    Devuelve una respuesta (redirección o 401) si hay que cerrar la sesión, o None.
    Si STOD no responde, la sesión continúa: una caída de STOD no debe sacar a todos.
    """
    usuario = current_user._get_current_object()
    limite = ahora_utc() - timedelta(minutes=current_app.config["STOD_REVALIDAR_MINUTOS"])
    if usuario.stod_verificado_en is not None and usuario.stod_verificado_en > limite:
        return None
    try:
        identidad = proveedor_identidad().consultar(usuario.usuario_stod)
    except IdentidadNoDisponible as exc:
        log.warning("No se pudo revalidar la sesión con STOD: %s", exc, extra={"evento": "auth.revalidacion_pendiente"})
        return None
    if identidad is not None and identidad.activo:
        usuario.stod_verificado_en = ahora_utc()
        db.session.commit()
        return None

    log.warning("Sesión cerrada: el usuario ya no está activo en STOD", extra={"evento": "auth.revalidacion_fallida"})
    return sesion.respuesta_cierre("stod")
