"""Pantallas del hub en celular (390 px): lo que solo se ve con un navegador real midiendo."""
import pytest
from playwright.sync_api import Page

from .conftest import entrar

CELULAR = {"width": 390, "height": 844}
# Pantallas con botones en el encabezado (macro «encabezado» con caller): las más expuestas.
PANTALLAS = ["/m/expedientes_seguros/", "/m/corte_caja/", "/admin/usuarios"]


@pytest.mark.parametrize("ruta", PANTALLAS)
def test_los_botones_del_encabezado_no_tapan_el_titulo(page: Page, servidor, errores_js, ruta):
    # Hallado en QA (26/11/2026): a 390 px la columna del título se encogía a ~35 px y los botones
    # quedaban encima. Ahora los botones bajan a su propia línea.
    entrar(page, servidor.url, "qa_super")
    page.set_viewport_size(CELULAR)
    page.goto(servidor.url + ruta)
    titulo = page.locator(".page-header .page-title").first.bounding_box()
    assert titulo["width"] >= 150, f"El título mide {titulo['width']:.0f} px de ancho"
    for boton in page.locator(".page-header .btn-list > *").all():
        caja = boton.bounding_box()
        se_cruzan = not (caja["x"] >= titulo["x"] + titulo["width"] or caja["x"] + caja["width"] <= titulo["x"]
                         or caja["y"] >= titulo["y"] + titulo["height"] or caja["y"] + caja["height"] <= titulo["y"])
        assert not se_cruzan, f"Un botón del encabezado tapa el título en {ruta}"
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), "La página se desborda"
