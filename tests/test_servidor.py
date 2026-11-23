"""Opciones de Waitress en serve.py: publicación detrás de un proxy (docs/DESPLIEGUE.md)."""
from waitress.adjustments import Adjustments

from serve import opciones_servidor


def test_sin_variables_escucha_solo_en_el_equipo():
    opciones = opciones_servidor({})
    assert opciones == {"host": "127.0.0.1", "port": 8000, "threads": 8}
    Adjustments(**opciones)  # Waitress las acepta


def test_variables_vacias_usan_los_valores_por_defecto():
    assert opciones_servidor({"HOST": "", "PORT": "", "HILOS": "", "PROXY_CONFIABLE": " "}) == opciones_servidor({})


def test_con_proxy_confia_en_su_ip_real_y_https():
    opciones = opciones_servidor({"PORT": "8010", "HILOS": "16", "PROXY_CONFIABLE": "127.0.0.1"})
    ajustes = Adjustments(**opciones)
    assert ajustes.port == 8010 and ajustes.threads == 16
    assert ajustes.trusted_proxy == "127.0.0.1"
    assert ajustes.trusted_proxy_headers == {"x-forwarded-for", "x-forwarded-proto"}
    # Las cabeceras X-Forwarded-* de cualquier otro origen se descartan: no se puede falsear la IP.
    assert ajustes.clear_untrusted_proxy_headers is True
