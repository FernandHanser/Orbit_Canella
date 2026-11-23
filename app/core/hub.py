"""Pantallas generales del hub."""
from __future__ import annotations

from dataclasses import dataclass

from flask import Blueprint, jsonify, render_template
from flask_login import current_user

from app.core.catalogo import ModuloDisponible, modulos_de_usuario
from app.core.ejecuciones import ResumenEjecucion, ultimas_ejecuciones

bp = Blueprint("hub", __name__)


@dataclass(frozen=True)
class Tarjeta:
    """Lo que muestra la tarjeta de un módulo en el inicio: qué es y cuándo corrió por última vez."""

    modulo: ModuloDisponible
    ultima: ResumenEjecucion | None       # incluye "sin_cambios": muestra que el robot sigue vivo


@bp.route("/")
def inicio():
    tarjetas = []
    for m in modulos_de_usuario(current_user):
        ultimas = ultimas_ejecuciones(m.definicion.id, limite=1, incluir_sin_cambios=True)
        tarjetas.append(Tarjeta(m, ultimas[0] if ultimas else None))
    return render_template("hub/inicio.html", tarjetas=tarjetas)


@bp.route("/salud")
def salud():
    # Público y sin detalles internos: solo para monitoreo de disponibilidad.
    return jsonify(estado="ok")
