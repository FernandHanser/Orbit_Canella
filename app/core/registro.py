"""Registro de módulos de negocio.

Cada paquete en ``app/modulos/<id>/`` expone en su ``__init__.py`` una variable
``MODULO`` de tipo :class:`DefinicionModulo`. El hub la descubre al arrancar, monta su
Blueprint bajo ``/m/<id>`` y protege **todas** sus rutas (web y API) con la
verificación de permisos del núcleo. El módulo no necesita decoradores de seguridad.

Ejemplo mínimo::

    bp = Blueprint("conciliacion", __name__, template_folder="templates")

    MODULO = DefinicionModulo(
        id="conciliacion",
        nombre="Conciliación bancaria",
        descripcion="Concilia estados de cuenta contra SAP.",
        icono="building-bank",          # nombre de Tabler Icons sin el prefijo "ti-"
        blueprint=bp,
        vista_inicio="inicio",          # endpoint conciliacion.inicio
        tareas={"conciliar": conciliar},  # opcional: tareas ejecutables sin sesión web
    )
"""
from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from flask import Blueprint, Flask, current_app

from app.core.logs import get_logger

PATRON_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
IDS_RESERVADOS = {"core", "admin", "auth", "hub", "static", "api", "sistema"}
CLAVE_EXTENSION = "automate_modulos"

log = get_logger("core")


@dataclass(frozen=True)
class DefinicionModulo:
    id: str
    nombre: str
    descripcion: str
    icono: str
    blueprint: Blueprint
    vista_inicio: str = "inicio"
    ruta: str | None = None
    permiso: str | None = None
    tareas: Mapping[str, Callable[..., Any]] = field(default_factory=dict)
    version: str = "0.1.0"
    es_ejemplo: bool = False

    def __post_init__(self) -> None:
        if not PATRON_ID.match(self.id) or self.id in IDS_RESERVADOS:
            raise ValueError(f"Identificador de módulo inválido: {self.id!r}")
        if self.blueprint.name != self.id:
            raise ValueError(
                f"El Blueprint del módulo {self.id!r} debe llamarse igual que el módulo "
                f"(se llama {self.blueprint.name!r})."
            )
        # Ruta y permiso se derivan del id y no se pueden cambiar: con otra ruta, un módulo podría
        # montarse sobre /admin o sobre las URLs de otro módulo (Flask atiende al primero que se
        # registró); con otro permiso, se presentaría con el permiso de otro módulo.
        for campo, esperado in (("ruta", f"/m/{self.id}"), ("permiso", f"modulo.{self.id}")):
            valor = getattr(self, campo)
            if valor is None:
                object.__setattr__(self, campo, esperado)
            elif valor != esperado:
                raise ValueError(
                    f"El módulo {self.id!r} no puede usar {campo}={valor!r}: debe ser {esperado!r}."
                )

    @property
    def endpoint_inicio(self) -> str:
        return f"{self.id}.{self.vista_inicio}"


class RegistroModulos:
    def __init__(self) -> None:
        self._modulos: dict[str, DefinicionModulo] = {}

    def registrar(self, app: Flask, definicion: DefinicionModulo) -> None:
        if definicion.id in self._modulos:
            raise ValueError(f"Módulo duplicado: {definicion.id}")
        app.register_blueprint(definicion.blueprint, url_prefix=definicion.ruta)
        self._modulos[definicion.id] = definicion

    def obtener(self, modulo_id: str | None) -> DefinicionModulo | None:
        if modulo_id is None:
            return None
        return self._modulos.get(modulo_id)

    def todos(self) -> list[DefinicionModulo]:
        return sorted(self._modulos.values(), key=lambda m: m.nombre.lower())

    def __contains__(self, modulo_id: str) -> bool:
        return modulo_id in self._modulos


def registro(app: Flask | None = None) -> RegistroModulos:
    return (app or current_app).extensions[CLAVE_EXTENSION]


def _descubrir(nombre_paquete: str) -> list[str]:
    paquete = importlib.import_module(nombre_paquete)
    return [
        f"{paquete.__name__}.{info.name}"
        for info in pkgutil.iter_modules(paquete.__path__)
        if info.ispkg and not info.name.startswith("_")
    ]


def cargar_modulos(app: Flask, paquete: str) -> RegistroModulos:
    """Importa y registra los módulos configurados (``MODULOS``) o todos los del ``paquete``.

    El paquete lo indica ``create_app``: el núcleo no conoce dónde viven los módulos."""
    reg = RegistroModulos()
    app.extensions[CLAVE_EXTENSION] = reg
    rutas = app.config.get("MODULOS") or _descubrir(paquete)
    for ruta in rutas:
        try:
            paquete = importlib.import_module(ruta)
            definicion = getattr(paquete, "MODULO", None)
            if not isinstance(definicion, DefinicionModulo):
                raise TypeError(f"{ruta} no define MODULO = DefinicionModulo(...)")
            reg.registrar(app, definicion)
            log.debug("Módulo registrado: %s", definicion.id, extra={"evento": "modulo.registrado"})
        except Exception:
            # Un módulo defectuoso no debe tumbar el hub, salvo en pruebas.
            log.exception("No se pudo cargar el módulo %s", ruta, extra={"evento": "modulo.error_carga"})
            if app.config.get("TESTING"):
                raise
    return reg
