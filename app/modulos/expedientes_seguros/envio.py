"""Envío del correo del paquete por SMTP desde el buzón del hub.

Mismo mecanismo que CODA Reports (``services/email_service.py``) contra el Exchange de Canella:
STARTTLS, autenticación con la cuenta del buzón y reintentos ante fallas temporales (421 o tiempo
agotado). El contrato ``Enviador`` deja simularlo en las pruebas sin red.
"""
from __future__ import annotations

import smtplib
import socket
import time
from email.message import EmailMessage
from typing import Protocol

from .configuracion import ConfigCorreo

TIEMPO_ESPERA_S = 30
PAUSA_REINTENTO_S = 5


class CorreoNoEnviado(RuntimeError):
    """El servidor no aceptó el correo. El mensaje se puede mostrar al usuario."""


class Enviador(Protocol):
    def enviar(self, mensaje: EmailMessage) -> None: ...


def _explicar(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "el servidor de correo rechazó el usuario o la contraseña del buzón"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return f"el servidor rechazó los destinatarios: {', '.join(exc.recipients)}"
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return f"el servidor no permite enviar como {exc.sender} con esa cuenta"
    if isinstance(exc, smtplib.SMTPDataError) and exc.smtp_code == 552:
        return "el correo supera el tamaño máximo que acepta el servidor"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "tiempo de espera agotado con el servidor de correo"
    if isinstance(exc, socket.gaierror):
        return "no se pudo resolver el nombre del servidor de correo"
    if isinstance(exc, (ConnectionError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return "no se pudo conectar con el servidor de correo"
    return str(exc) or type(exc).__name__


def _temporal(exc: Exception) -> bool:
    codigo = getattr(exc, "smtp_code", None)
    return isinstance(exc, (TimeoutError, socket.timeout, smtplib.SMTPServerDisconnected)) or codigo == 421


class EnviadorSmtp:
    def __init__(self, config: ConfigCorreo) -> None:
        self._config = config

    def enviar(self, mensaje: EmailMessage) -> None:
        c = self._config
        intentos = max(c.intentos, 1)
        for intento in range(1, intentos + 1):
            try:
                with smtplib.SMTP(c.servidor, c.puerto, timeout=TIEMPO_ESPERA_S) as smtp:
                    smtp.ehlo()
                    if c.tls:
                        smtp.starttls()
                        smtp.ehlo()
                    if c.usuario:
                        smtp.login(c.usuario, c.contrasena)
                    smtp.send_message(mensaje)
                return
            except Exception as exc:
                if _temporal(exc) and intento < intentos:
                    time.sleep(PAUSA_REINTENTO_S)
                    continue
                raise CorreoNoEnviado(f"No se envió el correo: {_explicar(exc)}.") from exc
