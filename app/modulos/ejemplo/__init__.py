"""Módulo de EJEMPLO (demostración técnica, sin lógica contable real).

Muestra el contrato de un módulo del hub:
* ``views.py``    → Blueprint raíz con las pantallas (``/m/ejemplo/``).
* ``api.py``      → Blueprint anidado con la API (``/m/ejemplo/api/...``).
* ``services.py`` → lógica del módulo, independiente de Flask.
* ``templates/ejemplo/`` → plantillas propias que extienden la base del hub.

Puede eliminarse cuando existan módulos reales (ver docs/AGREGAR_MODULO.md).
"""
from app.core.registro import DefinicionModulo

from . import api  # noqa: F401  (registra la API dentro del Blueprint del módulo)
from .services import tarea_demo
from .views import bp

MODULO = DefinicionModulo(
    id="ejemplo",
    nombre="Módulo de ejemplo",
    descripcion="Demostración técnica del registro, la protección de rutas, las ejecuciones y los logs. No procesa datos contables.",
    icono="flask",
    blueprint=bp,
    vista_inicio="inicio",
    tareas={"demo": tarea_demo},
    version="1.0.0",
    es_ejemplo=True,
)
