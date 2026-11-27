"""Corte de caja diario.

Recibe por correo los cortes de caja de las agencias, valida asunto y adjuntos, archiva los
archivos en la carpeta de la empresa con su estructura oficial (``Vesa/1.Año 2026/202611NOVIEMBRE/27-11-26``),
registra los avisos de «sin movimiento» y responde con un rechazo explicado cuando algo no cumple.
Migrado del prototipo ``RicardoCruzLemus/AUTOMATIZACION_CORTE_DE_CAJA_DIARIO`` (rama ``dev``,
actualizado hasta ``9f62359``).

* ``reglas.py``        → reglas de negocio puras.
* ``buzon.py``         → contrato ``Buzon`` y adaptador EWS (el buzón es la cola).
* ``archivador.py``    → escritura idempotente en la carpeta compartida.
* ``servicios.py``     → tarea ``procesar``.
* ``views.py``         → tablero: Procesadas, Rechazadas y Cuadre mensual (``cuadre.py``).
* ``directorio.py``    → configuración: directorio de cajas y tiendas.
* ``cli.py``           → empresas (carpetas de destino) y carga del directorio, por consola.

Guía completa: docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md.
"""
from app.core.registro import DefinicionModulo

from . import cli  # noqa: F401  (registra los comandos del módulo en el Blueprint)
from . import directorio  # noqa: F401  (registra las pantallas del directorio en el Blueprint)
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
    version="1.2.0",
)
