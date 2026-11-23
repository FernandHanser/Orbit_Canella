"""Servidor para ambientes distintos a desarrollo (Waitress, compatible con Windows).

    AUTOMATE_ENV=production python serve.py

Variables (solo de este archivo): HOST (127.0.0.1), PORT (8000), HILOS (8) y PROXY_CONFIABLE.
Publicación detrás de IIS con HTTPS: ver docs/DESPLIEGUE.md.
"""
import os

# Cabeceras que el proxy agrega y que Waitress solo acepta si vienen de PROXY_CONFIABLE:
# la IP real del usuario (el bloqueo de login cuenta intentos por IP) y que llegó por HTTPS.
CABECERAS_PROXY = {"x-forwarded-for", "x-forwarded-proto"}


def opciones_servidor(entorno=os.environ) -> dict:
    """Argumentos para ``waitress.serve`` a partir de las variables de entorno."""
    opciones = {
        "host": entorno.get("HOST") or "127.0.0.1",
        "port": int(entorno.get("PORT") or "8000"),
        "threads": int(entorno.get("HILOS") or "8"),
    }
    proxy = (entorno.get("PROXY_CONFIABLE") or "").strip()
    if proxy:
        opciones.update(
            trusted_proxy=proxy,
            trusted_proxy_count=1,
            trusted_proxy_headers=CABECERAS_PROXY,
            # Sin esto, un usuario podría mandar su propio X-Forwarded-For y saltarse el bloqueo.
            clear_untrusted_proxy_headers=True,
        )
    return opciones


if __name__ == "__main__":
    from waitress import serve

    from app import create_app  # carga .env (app/config.py), así HOST/PORT/... ya están definidas

    serve(create_app(), **opciones_servidor())
