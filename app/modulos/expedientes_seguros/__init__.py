"""Expedientes de Seguros (Taller).

Con el número de la llamada de servicio y el centro de costo, trae de SAP el expediente PDF que
Taller adjuntó, lo muestra en miniaturas para elegir las páginas del paquete para Créditos y
Cobros, genera el PDF ``<llamada>_<aseguradora>_<fecha>.pdf`` (el original no se toca) y envía
el correo con la plantilla de la aseguradora desde el buzón del hub, o lo deja como borrador
``.eml`` para enviarlo desde Outlook.

* ``sap.py``           → contrato ``RepositorioSap`` y consultas de solo lectura a SBO_CANELLA.
* ``documentos.py``    → miniaturas (pypdfium2) y armado del PDF (pypdf).
* ``reglas.py``        → nombres de archivo, selección de páginas, plantilla y correo (puras).
* ``envio.py``         → contrato ``Enviador`` y envío por SMTP (Exchange, como CODA Reports).
* ``servicios.py``     → casos de uso, cachés y registro de paquetes.
* ``views.py``         → buscar, visor, generar, descargar y enviar; ``aseguradoras.py`` →
  configuración del correo (administradores); ``cli.py`` → ``probar-correo``.

Requerimiento: contexto/ y docs/PLAN_EXPEDIENTES_SEGUROS.md.
"""
from app.core.registro import DefinicionModulo

from . import aseguradoras  # noqa: F401  (registra las pantallas de configuración en el Blueprint)
from . import cli  # noqa: F401  (registra los comandos del módulo en el Blueprint)
from . import models  # noqa: F401  (registra las tablas para las migraciones)
from .views import bp

MODULO = DefinicionModulo(
    id="expedientes_seguros",
    nombre="Expedientes de Seguros (Taller)",
    descripcion="Arma el paquete para Cobros con las páginas del expediente en SAP y envía el correo.",
    icono="file-certificate",
    blueprint=bp,
    vista_inicio="inicio",
    version="1.0.0",
)
