"""Roles de la plataforma: fuente única de su nombre y de lo que permite cada uno.

Las pantallas (lista y formulario de usuarios, menú) leen de aquí; ``docs/GLOSARIO.md`` repite
las descripciones y ``tests/test_acceso.py`` verifica que coincidan. Cambiar lo que hace un rol
empieza en este archivo.

La clave es lo que se guarda en ``HUB_USUARIOS.rol`` y no cambia. El nombre visible sí puede
cambiar: el rol ``usuario`` se muestra como **Operador** para no confundirlo con la identidad
("usuario STOD").
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rol:
    clave: str
    nombre: str
    descripcion: str
    color: str            # color de Tabler para su etiqueta
    asignable_web: bool   # False: solo por consola


ROLES = (
    Rol("usuario", "Operador",
        "Opera los módulos que tenga asignados. No configura nada.",
        "secondary", True),
    Rol("admin", "Administrador",
        "Asigna módulos, habilita o deshabilita personas, configura los módulos y revisa ejecuciones y logs.",
        "primary", True),
    Rol("superadmin", "Superadministrador",
        "Todo lo del administrador, más nombrar administradores y habilitar o deshabilitar módulos. Se asigna solo por consola.",
        "red", False),
)
ROLES_POR_CLAVE = {r.clave: r for r in ROLES}
ROLES_ASIGNABLES_WEB = tuple(r for r in ROLES if r.asignable_web)
