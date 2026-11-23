"""Configuración del módulo: variables ``EXPEDIENTES_*`` del entorno (``.env``).

Se leen al usarse, no al importar: el hub carga el módulo aunque falten, y la pantalla muestra
qué variable falta. Las credenciales no tienen valor por defecto.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

_IDENTIFICADOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class ConfiguracionIncompleta(RuntimeError):
    pass


@dataclass(frozen=True)
class ConfigSap:
    servidor: str
    base: str
    usuario: str
    contrasena: str
    driver: str
    # Campos de usuario de OINV con la Serie y el Número FEL de la factura (por confirmar en SAP).
    campo_serie: str
    campo_numero: str


def _valor(nombre: str) -> str:
    return (os.environ.get(nombre) or "").strip()


def _identificador(nombre: str, defecto: str) -> str:
    """Nombre de columna configurable: se valida porque va dentro del SQL."""
    valor = _valor(nombre) or defecto
    if not _IDENTIFICADOR.match(valor):
        raise ConfiguracionIncompleta(f"{nombre} no es un nombre de columna válido.")
    return valor


def sap() -> ConfigSap:
    obligatorias = {
        "EXPEDIENTES_SAP_SERVIDOR": _valor("EXPEDIENTES_SAP_SERVIDOR"),
        "EXPEDIENTES_SAP_BASE": _valor("EXPEDIENTES_SAP_BASE"),
        "EXPEDIENTES_SAP_USUARIO": _valor("EXPEDIENTES_SAP_USUARIO"),
        "EXPEDIENTES_SAP_CONTRASENA": _valor("EXPEDIENTES_SAP_CONTRASENA"),
    }
    faltantes = [n for n, v in obligatorias.items() if not v]
    if faltantes:
        raise ConfiguracionIncompleta(f"Faltan variables en .env: {', '.join(faltantes)}")
    return ConfigSap(
        servidor=obligatorias["EXPEDIENTES_SAP_SERVIDOR"],
        base=obligatorias["EXPEDIENTES_SAP_BASE"],
        usuario=obligatorias["EXPEDIENTES_SAP_USUARIO"],
        contrasena=obligatorias["EXPEDIENTES_SAP_CONTRASENA"],
        driver=_valor("EXPEDIENTES_SAP_DRIVER") or "ODBC Driver 17 for SQL Server",
        campo_serie=_identificador("EXPEDIENTES_SAP_CAMPO_SERIE", "U_DoctoSerie"),
        campo_numero=_identificador("EXPEDIENTES_SAP_CAMPO_NUMERO", "U_DoctoNo"),
    )


@dataclass(frozen=True)
class ConfigCorreo:
    servidor: str
    puerto: int
    usuario: str          # vacío = sin autenticar (relay por IP)
    contrasena: str
    remitente: str        # "Nombre <buzon@canella.com.gt>" o solo el correo
    tls: bool             # STARTTLS antes de autenticar
    intentos: int         # ante fallas temporales (421, tiempo agotado)


def correo() -> ConfigCorreo:
    """Envío por SMTP desde el buzón del hub (Exchange de Canella, como CODA Reports)."""
    obligatorias = {
        "EXPEDIENTES_SMTP_SERVIDOR": _valor("EXPEDIENTES_SMTP_SERVIDOR"),
        "EXPEDIENTES_SMTP_REMITENTE": _valor("EXPEDIENTES_SMTP_REMITENTE"),
    }
    faltantes = [n for n, v in obligatorias.items() if not v]
    if faltantes:
        raise ConfiguracionIncompleta(f"Faltan variables en .env: {', '.join(faltantes)}")
    usuario, contrasena = _valor("EXPEDIENTES_SMTP_USUARIO"), _valor("EXPEDIENTES_SMTP_CONTRASENA")
    if bool(usuario) != bool(contrasena):
        raise ConfiguracionIncompleta("EXPEDIENTES_SMTP_USUARIO y EXPEDIENTES_SMTP_CONTRASENA van juntas (o ninguna).")
    return ConfigCorreo(
        servidor=obligatorias["EXPEDIENTES_SMTP_SERVIDOR"],
        puerto=int(_valor("EXPEDIENTES_SMTP_PUERTO") or "587"),
        usuario=usuario,
        contrasena=contrasena,
        remitente=obligatorias["EXPEDIENTES_SMTP_REMITENTE"],
        tls=(_valor("EXPEDIENTES_SMTP_TLS") or "1").lower() in ("1", "true", "si", "sí"),
        intentos=int(_valor("EXPEDIENTES_SMTP_INTENTOS") or "3"),
    )


def servidor_anexos() -> str:
    """Nombre o IP con que el hub llega al servidor de archivos de SAP. SAP guarda la ruta con el
    nombre que resuelve en su red (``Srv-sapcanella``); si desde el hub no resuelve, aquí va la IP."""
    return _valor("EXPEDIENTES_ANEXOS_SERVIDOR")


def ceco_por_defecto() -> str:
    """Centro de costo que viene escrito en el buscador (Taller de Pintura)."""
    return _valor("EXPEDIENTES_CECO_POR_DEFECTO") or "1602"


def retencion_dias() -> int:
    """Días que se guardan los paquetes generados antes de borrarlos (datos personales)."""
    return int(_valor("EXPEDIENTES_RETENCION_DIAS") or "7")
