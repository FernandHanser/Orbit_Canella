"""Contrato de identidad del hub.

El núcleo solo conoce este contrato; la implementación concreta (hoy STOD, en
``app/integraciones/stod.py``) se registra al crear la aplicación con
:func:`registrar_proveedor`. Así las dependencias van de ``integraciones`` hacia ``core``
y nunca al revés.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from flask import Flask, current_app

CLAVE_EXTENSION = "automate_identidad"


class IdentidadNoDisponible(RuntimeError):
    """El proveedor de identidad no respondió (red, credenciales del hub o servidor caído)."""


@dataclass(frozen=True)
class Identidad:
    user_id: str
    usuario: str          # tal como está en el proveedor
    email: str | None
    activo: bool          # puede iniciar sesión en el proveedor

    @property
    def nombre_visible(self) -> str:
        """El proveedor no guarda el nombre completo: se usa el correo antes de la @ (como CODA)."""
        base = self.email.split("@")[0] if self.email else self.usuario
        return base.replace(".", " ").upper()


class ProveedorIdentidad(Protocol):
    def autenticar(self, usuario: str, contrasena: str) -> Identidad | None:
        """Identidad si la contraseña es correcta (activa o no); None si no coincide."""

    def consultar(self, usuario: str) -> Identidad | None:
        """Estado actual del usuario, sin contraseña; None si no existe."""


def normalizar_usuario(usuario: str) -> str:
    return (usuario or "").strip().lower()


def registrar_proveedor(app: Flask, proveedor: ProveedorIdentidad) -> None:
    app.extensions[CLAVE_EXTENSION] = proveedor


def proveedor_identidad() -> ProveedorIdentidad:
    return current_app.extensions[CLAVE_EXTENSION]
