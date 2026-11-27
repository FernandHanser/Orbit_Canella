"""Historial del prototipo: convierte sus JSON en filas de CORTE_CAJA_CORREOS. Funciones puras.

Se usa una sola vez, al apagar el prototipo (``flask corte_caja historial-importar``). El prototipo
borraba lo que tenía más de 30 días, así que el historial que se trae es el que quedaba en sus
archivos. Diferencias con lo que guarda el hub:

* ``transfer_logs.json`` tiene un registro por **archivo** (los más viejos) o por correo con la
  lista de archivos (los más nuevos). Los primeros se reagrupan en su correo: mismo estado,
  asunto, remitente y carpeta, con pocos segundos entre uno y otro.
* No hay Message-ID: se arma uno estable con el contenido (``prototipo:<huella>``), así importar
  dos veces el mismo archivo no duplica nada.
* No hay huella ni tamaño de los archivos: sus nombres van a ``adjuntos`` y no se crean filas en
  CORTE_CAJA_ARCHIVOS (serían datos inventados).
* La hora estaba en hora de Guatemala (UTC−6, sin horario de verano); el hub guarda UTC.
* La fecha del corte casi nunca venía: se toma del asunto, de la carpeta de destino o del nombre
  del primer archivo.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence

from . import reglas

ZONA_PROTOTIPO = timezone(timedelta(hours=-6))
EJECUCION_IMPORTADA = "importado-prototipo"
SEGUNDOS_ENTRE_ARCHIVOS = 120     # archivos del mismo correo: el prototipo los guardaba uno tras otro
ESTADOS = {"EXITO": "procesado", "SIN MOVIMIENTO": "sin_movimiento", "IGNORADO": "ignorado", "ERROR": "error"}
_NOMBRES_DE_RELLENO = {"(sin movimiento)", "(sin adjuntos)"}
# Nombres de carpeta del prototipo que cambiaron en el hub (los demás solo cambian mayúsculas).
_ALIAS_CARPETA = {"mr. credit": "Mister Credit"}
_FECHA_CARPETA = re.compile(r"^(\d{2})-(\d{2})-(\d{4}|\d{2})$")


@dataclass(frozen=True)
class CorreoImportado:
    message_id: str
    asunto: str
    remitente: str
    recibido: datetime          # UTC sin zona
    estado: str
    motivo: str | None = None
    empresa: str | None = None
    fecha_corte: date | None = None
    adjuntos: tuple[str, ...] = field(default_factory=tuple)


def a_utc(texto: str) -> datetime:
    local = datetime.strptime(texto.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZONA_PROTOTIPO)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _identificador(*partes: str) -> str:
    return "prototipo:" + hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:40]


def _remitente(texto: str | None) -> str:
    texto = (texto or "").strip()
    return "" if texto.lower() == "desconocido" else texto.lower()


def _nombres(valor) -> list[str]:
    lista = valor if isinstance(valor, list) else [valor]
    return [str(n) for n in lista if n and str(n).strip().lower() not in _NOMBRES_DE_RELLENO]


def _partes_destino(destino: str | None) -> list[str]:
    return [p for p in re.split(r"[\\/]+", destino or "") if p]


def _empresa(destino: str | None, asunto: str, empresas: Sequence[reglas.Empresa]) -> str | None:
    por_nombre = {e.carpeta.lower(): e.carpeta for e in empresas}
    for parte in _partes_destino(destino):
        clave = parte.lower()
        if clave in _ALIAS_CARPETA:
            return _ALIAS_CARPETA[clave]
        if clave in por_nombre:
            return por_nombre[clave]
    return reglas.identificar_empresa(asunto, empresas)


def _fecha_corte(registro: dict, asunto: str, destino: str | None, nombres: Sequence[str]) -> date | None:
    explicita = (registro.get("fecha_corte") or "").strip()
    if explicita:
        fecha = reglas.extraer_fecha(explicita.replace("-", "/"))
        if fecha:
            return fecha
    fecha = reglas.extraer_fecha(asunto)
    if fecha:
        return fecha
    partes = _partes_destino(destino)
    if partes:
        m = _FECHA_CARPETA.match(partes[-1])
        if m:
            dia, mes, anio = m.groups()
            try:
                return date(int(anio) if len(anio) == 4 else 2000 + int(anio), int(mes), int(dia))
            except ValueError:
                pass
    for nombre in nombres:
        encontrada = reglas.fecha_de_archivo(nombre)
        if encontrada and encontrada[1]:
            return encontrada[1]
    return None


def _grupos(registros: Iterable[dict]) -> list[list[dict]]:
    """Reagrupa en correos los registros de un archivo cada uno; los que ya traen la lista de
    archivos son un correo por sí solos."""
    grupos: list[list[dict]] = []
    anterior = None
    for r in sorted(registros, key=lambda r: r.get("timestamp", "")):
        clave = (r.get("status"), r.get("asunto"), r.get("remitente"), r.get("destino"))
        momento = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
        es_lista = isinstance(r.get("filename"), list)
        if (not es_lista and anterior and anterior[0] == clave and not anterior[2]
                and (momento - anterior[1]).total_seconds() <= SEGUNDOS_ENTRE_ARCHIVOS):
            grupos[-1].append(r)
        else:
            grupos.append([r])
        anterior = (clave, momento, es_lista)
    return grupos


def convertir_procesados(registros: Iterable[dict], empresas: Sequence[reglas.Empresa]) -> tuple[list[CorreoImportado], list[str]]:
    """``transfer_logs.json`` → correos. Devuelve también los estados desconocidos que se omitieron."""
    correos, omitidos = [], []
    for grupo in _grupos(registros):
        primero = grupo[0]
        estado = ESTADOS.get((primero.get("status") or "").strip().upper())
        if estado is None:
            omitidos.append(str(primero.get("status")))
            continue
        asunto = (primero.get("asunto") or "").strip()
        nombres = [n for r in grupo for n in _nombres(r.get("filename"))]
        destino = primero.get("destino")
        motivo = None
        if estado in ("error", "ignorado"):
            motivo = "\n".join(dict.fromkeys((r.get("message") or "").strip() for r in grupo if r.get("message"))) or None
        elif estado == "sin_movimiento":
            motivo = "El remitente indicó que la caja no tuvo movimiento."
        correos.append(CorreoImportado(
            message_id=_identificador(estado, asunto, primero.get("remitente") or "", primero["timestamp"], *nombres[:1]),
            asunto=asunto[:500], remitente=_remitente(primero.get("remitente"))[:320], recibido=a_utc(primero["timestamp"]),
            estado=estado, motivo=motivo,
            empresa=_empresa(destino, asunto, empresas) if estado != "ignorado" else None,
            fecha_corte=_fecha_corte(primero, asunto, destino, nombres), adjuntos=tuple(nombres),
        ))
    return correos, omitidos


def convertir_rechazados(registros: Iterable[dict], empresas: Sequence[reglas.Empresa]) -> list[CorreoImportado]:
    """``rejected_logs.json`` → correos rechazados, con el motivo en texto plano (uno por línea).

    Varios correos del mismo remitente y asunto pueden caer en el mismo segundo: el identificador
    lleva también los archivos, y las copias exactas un número de aparición (el orden del archivo
    se conserva al importarlo de nuevo, así que el número no cambia)."""
    correos = []
    vistos: dict[str, int] = {}
    for r in sorted(registros, key=lambda r: r.get("timestamp", "")):
        asunto = (r.get("asunto") or "").strip()
        nombres = _nombres(r.get("archivos") or [])
        motivo = re.sub(r"<[^>]+>", "", r.get("motivo") or "")
        motivo = "\n".join(p.strip() for p in motivo.split(" / ") if p.strip()) or None
        base = _identificador("rechazado", asunto, r.get("remitente") or "", r["timestamp"], *nombres)
        vistos[base] = vistos.get(base, 0) + 1
        correos.append(CorreoImportado(
            message_id=base if vistos[base] == 1 else _identificador(base, str(vistos[base])),
            asunto=asunto[:500], remitente=_remitente(r.get("remitente"))[:320], recibido=a_utc(r["timestamp"]),
            estado="rechazado", motivo=motivo, empresa=reglas.identificar_empresa(asunto, empresas),
            fecha_corte=reglas.extraer_fecha(asunto), adjuntos=tuple(nombres),
        ))
    return correos
