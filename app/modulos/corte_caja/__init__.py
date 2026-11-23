"""Corte de caja diario.

Recibe por correo los cortes de caja de las agencias, valida asunto y adjuntos, archiva los
archivos en ``<Empresa>/<Año>/<Mes>/<DD-MM-AAAA>/`` de la carpeta compartida y responde con un
rechazo explicado cuando algo no cumple. Migrado del prototipo
``RicardoCruzLemus/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO`` (rama ``dev``).

* ``reglas.py``        → reglas de negocio puras.
* ``buzon.py``         → contrato ``Buzon`` y adaptador EWS (el buzón es la cola).
* ``archivador.py``    → escritura idempotente en la carpeta compartida.
* ``servicios.py``     → tarea ``procesar``.
* ``views.py``         → panel; ``empresas.py`` → CRUD de empresas (administradores);
  ``cli.py`` → lo mismo por consola.

Guía completa: docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md.
"""
from app.core.registro import DefinicionModulo

from . import cli  # noqa: F401  (registra los comandos del módulo en el Blueprint)
from . import empresas  # noqa: F401  (registra las pantallas de empresas en el Blueprint)
from . import models  # noqa: F401  (registra las tablas para las migraciones)
from .servicios import procesar
from .views import bp

MODULO = DefinicionModulo(
    id="corte_caja",
    nombre="Corte de caja diario",
    descripcion="Archiva los cortes que llegan por correo y rechaza los que no cumplen.",
    icono="cash-register",
    blueprint=bp,
    vista_inicio="inicio",
    tareas={"procesar": procesar},
    version="1.0.0",
)
