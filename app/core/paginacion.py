"""Paginación común para las pantallas del hub y de los módulos.

* Consultas SQLAlchemy: ``consulta.paginate(page=pagina_actual(), per_page=POR_PAGINA, error_out=False)``.
* Listas ya cargadas (p. ej. eventos de log): ``PaginaLista(lista, pagina_actual(), POR_PAGINA)``.

``POR_PAGINA`` es el tamaño de página de todo el hub (núcleo y módulos).

Ambos objetos exponen ``page``, ``pages``, ``per_page``, ``total``, ``items``, ``has_prev``
y ``has_next``, que es lo que usa la macro ``paginacion`` de ``_macros.html``.
"""

from __future__ import annotations

from math import ceil
from typing import Sequence, TypeVar

from flask import request, url_for

POR_PAGINA = 15  # filas por página en todas las listas del hub

T = TypeVar("T")
PARAMETRO = "pagina"


def pagina_actual() -> int:
    return max(request.args.get(PARAMETRO, 1, type=int) or 1, 1)


def url_pagina(numero: int) -> str:
    """URL de la vista actual en la página indicada, conservando los filtros."""
    argumentos = {**(request.view_args or {}), **request.args.to_dict(), PARAMETRO: numero}
    return url_for(request.endpoint, **argumentos)


class PaginaLista:
    def __init__(self, elementos: Sequence[T], pagina: int, por_pagina: int):
        self.total = len(elementos)
        self.per_page = por_pagina
        self.pages = max(ceil(self.total / por_pagina), 1)
        self.page = min(max(pagina, 1), self.pages)
        inicio = (self.page - 1) * por_pagina
        self.items = list(elementos[inicio : inicio + por_pagina])

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages
