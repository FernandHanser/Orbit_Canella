"""Corte de caja en un navegador real: lo que depende de JavaScript (la confirmación al eliminar)."""
from playwright.sync_api import Page, expect

from .conftest import entrar


def _caja(servidor, nombre: str) -> int:
    from app.extensions import db
    from app.modulos.corte_caja.models import Caja

    with servidor.app.app_context():
        caja = Caja(categoria="CAJAS QA", nombre_caja=nombre, responsable="Olga QA", correo="cajaqa@canella.test")
        db.session.add(caja)
        db.session.commit()
        return caja.id


def _existe(servidor, caja_id: int) -> bool:
    from app.extensions import db
    from app.modulos.corte_caja.models import Caja

    with servidor.app.app_context():
        return db.session.get(Caja, caja_id) is not None


def test_eliminar_una_tienda_pide_confirmacion_y_cancelar_no_borra(page: Page, servidor, errores_js):
    caja_id = _caja(servidor, "TIENDA QA CONFIRMAR")
    entrar(page, servidor.url, "qa_operador")
    page.goto(f"{servidor.url}/m/corte_caja/cajas?texto=TIENDA QA CONFIRMAR")
    fila = page.locator("tr", has_text="TIENDA QA CONFIRMAR")

    fila.get_by_role("button", name="Eliminar").click()
    modal = page.locator("#modal-confirmar")
    expect(modal).to_be_visible()
    expect(modal).to_contain_text("¿Eliminar TIENDA QA CONFIRMAR?")
    modal.get_by_role("button", name="Cancelar").click()
    expect(modal).to_be_hidden()
    expect(fila).to_be_visible()
    assert _existe(servidor, caja_id)

    fila.get_by_role("button", name="Eliminar").click()
    modal.get_by_role("button", name="Sí, eliminar").click()
    expect(page.locator("tr", has_text="TIENDA QA CONFIRMAR")).to_have_count(0)
    assert not _existe(servidor, caja_id)
