"""Comandos del módulo: ``flask --app wsgi corte_caja <comando>``.

La lista de empresas se administra por consola mientras el hub no tenga permisos más finos que
"acceso al módulo" (pendiente en docs/PLAN_DE_TRABAJO.md).
"""
from __future__ import annotations

from datetime import timedelta

import click

from app.core.logs import get_logger
from app.extensions import db

from . import reglas
from .models import Caja, Empresa
from .views import bp

log = get_logger("corte_caja")
_AYUDA_PLANTILLA = "Subcarpetas por fecha, separadas por /. Fichas: {AAAA} {AA} {MM} {MES} {Mes} {DD}."


def _buscar(carpeta: str) -> Empresa:
    empresa = Empresa.query.filter_by(carpeta=carpeta).first()
    if empresa is None:
        raise click.ClickException(f"No existe la empresa {carpeta!r}. Consulta: flask --app wsgi corte_caja empresas")
    return empresa


def _plantilla_valida(plantilla: str) -> str:
    error = reglas.validar_plantilla(plantilla)
    if error:
        raise click.ClickException(f"Plantilla inválida: {error}")
    return plantilla.strip()


def _registrar(evento: str, empresa: Empresa) -> None:
    db.session.commit()
    log.info("Empresa actualizada desde CLI", extra={"evento": evento, "usuario": "proceso:cli", "datos": {
        "carpeta": empresa.carpeta, "palabras_clave": empresa.palabras_clave, "orden": empresa.orden, "activa": empresa.activa,
        "plantilla_carpeta": empresa.plantilla_carpeta}})


@bp.cli.command("empresas")
def empresas() -> None:
    """Lista las empresas, en el orden en que se buscan en el asunto."""
    for e in Empresa.query.order_by(Empresa.orden, Empresa.carpeta):
        click.echo(f"{e.orden:>4}  {e.carpeta:<20} {'activa' if e.activa else 'inactiva':<9} "
                   f"subcarpetas: {e.plantilla_carpeta}  claves: {e.palabras_clave}")


@bp.cli.command("empresa-agregar")
@click.argument("carpeta")
@click.option("--claves", required=True, help="Palabras clave separadas por coma (sin tildes ni mayúsculas importan).")
@click.option("--orden", type=int, default=100, show_default=True, help="La primera empresa que coincide gana.")
@click.option("--plantilla", default=reglas.PLANTILLA_ESTANDAR, show_default=True, help=_AYUDA_PLANTILLA)
def empresa_agregar(carpeta: str, claves: str, orden: int, plantilla: str) -> None:
    """Agrega una empresa. CARPETA es el nombre exacto de su carpeta en el destino."""
    if Empresa.query.filter_by(carpeta=carpeta).first():
        raise click.ClickException(f"La empresa {carpeta!r} ya existe; usa empresa-modificar.")
    empresa = Empresa(carpeta=carpeta, palabras_clave=claves, orden=orden, activa=True,
                      plantilla_carpeta=_plantilla_valida(plantilla))
    db.session.add(empresa)
    _registrar("corte_caja.empresa_agregada", empresa)
    click.echo(f"Empresa {carpeta!r} agregada.")


@bp.cli.command("empresa-modificar")
@click.argument("carpeta")
@click.option("--claves", help="Nuevas palabras clave separadas por coma (reemplazan las actuales).")
@click.option("--orden", type=int)
@click.option("--activa/--inactiva", default=None)
@click.option("--plantilla", help=_AYUDA_PLANTILLA)
def empresa_modificar(carpeta: str, claves: str | None, orden: int | None, activa: bool | None, plantilla: str | None) -> None:
    """Cambia palabras clave, orden, estado o subcarpetas de una empresa."""
    empresa = _buscar(carpeta)
    if claves is not None:
        empresa.palabras_clave = claves
    if orden is not None:
        empresa.orden = orden
    if activa is not None:
        empresa.activa = activa
    if plantilla is not None:
        empresa.plantilla_carpeta = _plantilla_valida(plantilla)
    _registrar("corte_caja.empresa_modificada", empresa)
    click.echo(f"Empresa {carpeta!r} actualizada.")


@bp.cli.command("cajas-importar")
@click.argument("ruta", type=click.Path(exists=True, dir_okay=False))
def cajas_importar(ruta: str) -> None:
    """Carga el directorio de cajas desde el ``cajas.db`` del prototipo (tabla ``cajas_directorio``).

    El archivo se abre en solo lectura. Las cajas que ya existen (misma categoría, nombre y correo)
    no se repiten, así que se puede volver a correr. El directorio tiene nombres y correos de
    personas: por eso se carga por consola y no viaja en el repositorio ni en una migración."""
    import sqlite3
    from pathlib import Path

    uri = Path(ruta).resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as origen:
            filas = origen.execute("SELECT categoria, nombre_caja, responsable, correo FROM cajas_directorio ORDER BY id").fetchall()
    except sqlite3.Error as exc:
        raise click.ClickException(f"No se pudo leer cajas_directorio de {ruta}: {exc}")
    existentes = {(c.categoria, c.nombre_caja, c.correo or "") for c in Caja.query}
    nuevas = 0
    for categoria, nombre, responsable, correo in filas:
        categoria, nombre = " ".join((categoria or "").split()).upper(), " ".join((nombre or "").split())
        correo = (correo or "").strip() or None
        if not categoria or not nombre or (categoria, nombre, correo or "") in existentes:
            continue
        db.session.add(Caja(categoria=categoria[:100], nombre_caja=nombre[:150],
                            responsable=((responsable or "").strip() or None) and responsable.strip()[:150],
                            correo=correo and correo[:500]))
        existentes.add((categoria, nombre, correo or ""))
        nuevas += 1
    db.session.commit()
    log.info("Directorio de cajas importado desde CLI", extra={"evento": "corte_caja.cajas_importadas", "usuario": "proceso:cli",
                                                              "datos": {"leidas": len(filas), "agregadas": nuevas}})
    click.echo(f"{len(filas)} cajas leídas, {nuevas} agregadas, {len(filas) - nuevas} ya existían u omitidas.")


@bp.cli.command("historial-importar")
@click.option("--procesados", type=click.Path(exists=True, dir_okay=False), help="transfer_logs.json del prototipo.")
@click.option("--rechazados", type=click.Path(exists=True, dir_okay=False), help="rejected_logs.json del prototipo.")
def historial_importar(procesados: str | None, rechazados: str | None) -> None:
    """Trae al tablero el historial del prototipo (sus JSON). Se corre al apagarlo.

    Los archivos se leen sin modificarlos. Lo ya importado no se repite (Message-ID estable), así
    que se puede volver a correr con archivos más nuevos. Ver historial.py para lo que cambia."""
    import json
    from collections import Counter

    from . import historial
    from .models import Correo

    if not procesados and not rechazados:
        raise click.ClickException("Indica --procesados, --rechazados o ambos.")

    def leer(ruta: str) -> list[dict]:
        try:
            with open(ruta, encoding="utf-8-sig") as f:
                datos = json.load(f)
        except (OSError, ValueError) as exc:
            raise click.ClickException(f"No se pudo leer {ruta}: {exc}")
        if not isinstance(datos, list):
            raise click.ClickException(f"{ruta} no tiene una lista de registros.")
        return datos

    empresas = [reglas.Empresa(e.carpeta, e.lista_claves, e.plantilla_carpeta) for e in Empresa.query]
    correos, omitidos = [], []
    if procesados:
        convertidos, omitidos = historial.convertir_procesados(leer(procesados), empresas)
        correos += convertidos
    if rechazados:
        correos += historial.convertir_rechazados(leer(rechazados), empresas)

    existentes = {m for (m,) in db.session.query(Correo.message_id).filter(Correo.ejecucion_id == historial.EJECUCION_IMPORTADA)}
    nuevos = [c for c in correos if c.message_id not in existentes]
    for c in nuevos:
        db.session.add(Correo(
            ejecucion_id=historial.EJECUCION_IMPORTADA, message_id=c.message_id, asunto=c.asunto, remitente=c.remitente,
            recibido=c.recibido, estado=c.estado, motivo=c.motivo, empresa=c.empresa, fecha_corte=c.fecha_corte,
            adjuntos="\n".join(c.adjuntos) or None, simulado=False,
        ))
    db.session.commit()
    conteo = Counter(c.estado for c in nuevos)
    log.info("Historial del prototipo importado desde CLI", extra={"evento": "corte_caja.historial_importado", "usuario": "proceso:cli",
                                                                   "datos": {"leidos": len(correos), "agregados": dict(conteo)}})
    click.echo(f"{len(correos)} correos en los archivos, {len(nuevos)} agregados, {len(correos) - len(nuevos)} ya estaban.")
    for estado, n in sorted(conteo.items()):
        click.echo(f"  {estado:<15} {n}")
    if omitidos:
        click.echo(f"  Omitidos por estado desconocido: {dict(Counter(omitidos))}")
    if correos:
        ultimo = max(c.recibido for c in correos)
        click.echo(f"Último correo del prototipo: {ultimo:%Y-%m-%dT%H:%M} UTC. Para no reprocesar la bandeja de entrada: "
                   f"CORTE_CAJA_RECIBIDOS_DESDE={(ultimo + timedelta(minutes=1)):%Y-%m-%dT%H:%M}")
