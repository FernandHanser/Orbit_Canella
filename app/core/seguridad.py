"""Cabeceras de seguridad HTTP. Las contraseñas las valida STOD (app/integraciones/stod.py)."""
from __future__ import annotations

import mimetypes

from flask import Flask, request

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "form-action 'self'; base-uri 'self'; object-src 'none'"
)


def instalar_cabeceras(app: Flask) -> None:
    # En Windows, Python toma el tipo de cada extensión del registro, y algunos equipos tienen
    # «.js = text/plain». Con «nosniff» el navegador se niega a ejecutar esos scripts y el hub se
    # queda sin menú, confirmaciones ni aviso de sesión. El tipo de .js no depende del equipo.
    mimetypes.add_type("text/javascript", ".js")

    @app.after_request
    def _cabeceras(respuesta):
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "DENY")
        respuesta.headers.setdefault("Referrer-Policy", "same-origin")
        respuesta.headers.setdefault("Content-Security-Policy", CSP)
        if request.endpoint != "static":
            # Evita que el botón "atrás" muestre datos tras cerrar sesión.
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta
