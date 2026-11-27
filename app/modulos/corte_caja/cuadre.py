"""Cuadre mensual por caja. Funciones puras: sin Flask ni base de datos.

Traslado de la lógica del tablero del prototipo (``index.html``: ``getCajaNameForLog``,
``_runCuadre``, ``renderCalendar``, ``_showCortesForDate``). Un correo se atribuye a una caja del
directorio por, en este orden:

1. el remitente es uno de los correos de la caja;
2. el nombre completo de la caja aparece en el asunto o en la carpeta donde se guardó;
3. alguna palabra distintiva del nombre (5 letras o más, sin las genéricas) aparece ahí.

Corrección respecto al prototipo: comparaba el remitente con cualquier palabra del campo correo,
así que «se turnan los cobradores» (texto en lugar de correo) hacía coincidir con la caja
cualquier remitente que contuviera «se». Aquí solo cuentan las direcciones con ``@`` y se
comparan completas.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

RECIBIDO = "recibido"
SIN_MOVIMIENTO = "sin_movimiento"
NO_RECIBIDO = "no_recibido"
FUTURO = "futuro"

# Palabras que no distinguen a una caja de otra (las del prototipo).
_GENERICAS_RECHAZO = {"caja", "cajas", "tienda", "canella"}
_GENERICAS_CUADRE = _GENERICAS_RECHAZO | {"repuestos"}


@dataclass(frozen=True)
class CajaDirectorio:
    nombre: str
    correo: str | None = None


@dataclass(frozen=True)
class Registro:
    """Un correo ya procesado, con lo necesario para atribuirlo a una caja."""

    fecha: date               # fecha del corte (o del día en que llegó, si no se supo)
    estado: str               # RECIBIDO o SIN_MOVIMIENTO
    remitente: str
    asunto: str
    destino: str = ""         # carpetas donde se guardaron sus archivos


def correos(texto: str | None) -> set[str]:
    return {t for t in re.split(r"[\s,;/]+", (texto or "").lower()) if "@" in t}


def _coincide_nombre(nombre: str, textos: Iterable[str], genericas: set[str]) -> bool:
    nombre = (nombre or "").lower().strip()
    if len(nombre) < 3:
        return False
    textos = [t.lower() for t in textos if t]
    if any(nombre in t for t in textos):
        return True
    palabras = [p for p in nombre.split() if len(p) >= 5 and p not in genericas]
    return any(p in t for p in palabras for t in textos)


def caja_de(remitente: str | None, asunto: str | None, cajas: Sequence[CajaDirectorio]) -> str | None:
    """Nombre de la caja de un correo (columna «Caja» de los rechazados), o ``None``."""
    remitente = (remitente or "").lower().strip()
    if remitente:
        for caja in cajas:
            if remitente in correos(caja.correo):
                return caja.nombre
    for caja in cajas:   # primero el nombre completo en todas, después las palabras
        nombre = (caja.nombre or "").lower().strip()
        if len(nombre) >= 3 and nombre in (asunto or "").lower():
            return caja.nombre
    for caja in cajas:
        if _coincide_nombre(caja.nombre, [asunto or ""], _GENERICAS_RECHAZO):
            return caja.nombre
    return None


def es_de_la_caja(caja: CajaDirectorio, registro: Registro) -> bool:
    if registro.remitente and registro.remitente.lower().strip() in correos(caja.correo):
        return True
    return _coincide_nombre(caja.nombre, [registro.asunto, registro.destino], _GENERICAS_CUADRE)


def estado_del_dia(dia: date, registros: Sequence[Registro], hoy: date) -> str:
    """Color del día en el calendario: futuro, sin ningún corte, solo «sin movimiento» o con cortes."""
    if dia > hoy:
        return FUTURO
    if not registros:
        return NO_RECIBIDO
    return SIN_MOVIMIENTO if all(r.estado == SIN_MOVIMIENTO for r in registros) else RECIBIDO


def estado_de_la_caja(caja: CajaDirectorio, registros_del_dia: Sequence[Registro]) -> str:
    """Un corte recibido pesa más que un aviso de «sin movimiento» del mismo día."""
    propios = [r for r in registros_del_dia if es_de_la_caja(caja, r)]
    if any(r.estado == RECIBIDO for r in propios):
        return RECIBIDO
    return SIN_MOVIMIENTO if propios else NO_RECIBIDO


def dia_inicial(anio: int, mes: int, hoy: date) -> date:
    """Día que se muestra al abrir un mes: hoy en el mes actual, el último en uno pasado y el
    primero en uno futuro (como el prototipo)."""
    if (anio, mes) == (hoy.year, hoy.month):
        return hoy
    if (anio, mes) < (hoy.year, hoy.month):
        return date(anio, mes, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, 1)


def semanas(anio: int, mes: int) -> list[list[date | None]]:
    """Semanas del mes de lunes a domingo, con ``None`` en los huecos."""
    return [[d if d.month == mes else None for d in semana]
            for semana in calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)]
