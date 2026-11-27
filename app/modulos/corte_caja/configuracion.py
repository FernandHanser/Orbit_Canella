"""Configuración del módulo: variables ``CORTE_CAJA_*`` del entorno (``.env``).

Se leen al ejecutar la tarea, no al importar: el hub carga el módulo aunque falten, y la
ejecución falla con un mensaje claro. Las credenciales no tienen valor por defecto.

El modo simulación se retiró el 27/11/2026: la tarea siempre responde, guarda y mueve correos.
``CORTE_CAJA_MODO`` ya no se lee.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime


class ConfiguracionIncompleta(RuntimeError):
    pass


@dataclass(frozen=True)
class Configuracion:
    destino: str
    buzon: str
    ews_servidor: str
    ews_usuario: str
    ews_contrasena: str
    ews_proxy: str | None
    dominios: tuple[str, ...]
    lote: int
    recibidos_desde: datetime | None


def _valor(nombre: str) -> str:
    return (os.environ.get(nombre) or "").strip()


def leer() -> Configuracion:
    obligatorias = {
        "CORTE_CAJA_DESTINO": _valor("CORTE_CAJA_DESTINO"),
        "CORTE_CAJA_BUZON": _valor("CORTE_CAJA_BUZON"),
        "CORTE_CAJA_EWS_SERVIDOR": _valor("CORTE_CAJA_EWS_SERVIDOR"),
        "CORTE_CAJA_EWS_USUARIO": _valor("CORTE_CAJA_EWS_USUARIO"),
        "CORTE_CAJA_EWS_CONTRASENA": _valor("CORTE_CAJA_EWS_CONTRASENA"),
    }
    faltantes = [nombre for nombre, valor in obligatorias.items() if not valor]
    if faltantes:
        raise ConfiguracionIncompleta(f"Faltan variables en .env: {', '.join(faltantes)}")
    desde = _valor("CORTE_CAJA_RECIBIDOS_DESDE")
    try:
        recibidos_desde = datetime.fromisoformat(desde) if desde else None
    except ValueError:
        raise ConfiguracionIncompleta("CORTE_CAJA_RECIBIDOS_DESDE debe tener el formato AAAA-MM-DD o AAAA-MM-DDTHH:MM (UTC).")
    dominios = tuple(d.strip().lower() for d in (_valor("CORTE_CAJA_DOMINIOS") or "canella.com.gt").split(",") if d.strip())
    return Configuracion(
        destino=obligatorias["CORTE_CAJA_DESTINO"],
        buzon=obligatorias["CORTE_CAJA_BUZON"],
        ews_servidor=obligatorias["CORTE_CAJA_EWS_SERVIDOR"],
        ews_usuario=obligatorias["CORTE_CAJA_EWS_USUARIO"],
        ews_contrasena=obligatorias["CORTE_CAJA_EWS_CONTRASENA"],
        ews_proxy=_valor("CORTE_CAJA_EWS_PROXY") or None,
        dominios=dominios,
        lote=int(_valor("CORTE_CAJA_LOTE") or "20"),
        recibidos_desde=recibidos_desde,
    )
