"""Comandos del módulo: ``flask --app wsgi expedientes_seguros <comando>``."""
from __future__ import annotations

import click

from . import configuracion, reglas
from .envio import CorreoNoEnviado, EnviadorSmtp
from .views import bp


@bp.cli.command("probar-correo")
@click.argument("destino")
def probar_correo(destino: str) -> None:
    """Envía un correo de prueba a DESTINO con la configuración EXPEDIENTES_SMTP_* del .env."""
    try:
        config = configuracion.correo()
    except configuracion.ConfiguracionIncompleta as exc:
        raise click.ClickException(str(exc)) from exc
    mensaje = reglas.correo_saliente(
        config.remitente, destino, "", "Prueba de envío · Expedientes de Seguros",
        "Correo de prueba enviado desde AUTOMATE (ORBIT Canella). Si lo recibes, el envío está listo.", [])
    click.echo(f"Enviando por {config.servidor}:{config.puerto} (TLS: {'sí' if config.tls else 'no'}) "
               f"como {config.remitente} con el usuario {config.usuario or '(sin autenticar)'}…")
    try:
        EnviadorSmtp(config).enviar(mensaje)
    except CorreoNoEnviado as exc:
        raise click.ClickException(f"{exc} Detalle: {exc.__cause__!r}") from exc
    click.echo(f"Enviado a {destino}.")
