"""Comandos del módulo: ``flask --app wsgi corte_caja <comando>``.

La lista de empresas se administra por consola mientras el hub no tenga permisos más finos que
"acceso al módulo" (pendiente en docs/PLAN_DE_TRABAJO.md).
"""
from __future__ import annotations

import click

from app.core.logs import get_logger
from app.extensions import db

from .models import Empresa
from .views import bp

log = get_logger("corte_caja")


def _buscar(carpeta: str) -> Empresa:
    empresa = Empresa.query.filter_by(carpeta=carpeta).first()
    if empresa is None:
        raise click.ClickException(f"No existe la empresa {carpeta!r}. Consulta: flask --app wsgi corte_caja empresas")
    return empresa


def _registrar(evento: str, empresa: Empresa) -> None:
    db.session.commit()
    log.info("Empresa actualizada desde CLI", extra={"evento": evento, "usuario": "proceso:cli", "datos": {
        "carpeta": empresa.carpeta, "palabras_clave": empresa.palabras_clave, "orden": empresa.orden, "activa": empresa.activa}})


@bp.cli.command("empresas")
def empresas() -> None:
    """Lista las empresas, en el orden en que se buscan en el asunto."""
    for e in Empresa.query.order_by(Empresa.orden, Empresa.carpeta):
        click.echo(f"{e.orden:>4}  {e.carpeta:<20} {'activa' if e.activa else 'inactiva':<9} claves: {e.palabras_clave}")


@bp.cli.command("empresa-agregar")
@click.argument("carpeta")
@click.option("--claves", required=True, help="Palabras clave separadas por coma (sin tildes ni mayúsculas importan).")
@click.option("--orden", type=int, default=100, show_default=True, help="La primera empresa que coincide gana.")
def empresa_agregar(carpeta: str, claves: str, orden: int) -> None:
    """Agrega una empresa. CARPETA es el nombre exacto de su carpeta en el destino."""
    if Empresa.query.filter_by(carpeta=carpeta).first():
        raise click.ClickException(f"La empresa {carpeta!r} ya existe; usa empresa-modificar.")
    empresa = Empresa(carpeta=carpeta, palabras_clave=claves, orden=orden, activa=True)
    db.session.add(empresa)
    _registrar("corte_caja.empresa_agregada", empresa)
    click.echo(f"Empresa {carpeta!r} agregada.")


@bp.cli.command("empresa-modificar")
@click.argument("carpeta")
@click.option("--claves", help="Nuevas palabras clave separadas por coma (reemplazan las actuales).")
@click.option("--orden", type=int)
@click.option("--activa/--inactiva", default=None)
def empresa_modificar(carpeta: str, claves: str | None, orden: int | None, activa: bool | None) -> None:
    """Cambia palabras clave, orden o estado de una empresa."""
    empresa = _buscar(carpeta)
    if claves is not None:
        empresa.palabras_clave = claves
    if orden is not None:
        empresa.orden = orden
    if activa is not None:
        empresa.activa = activa
    _registrar("corte_caja.empresa_modificada", empresa)
    click.echo(f"Empresa {carpeta!r} actualizada.")
