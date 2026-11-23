"""Servidor para ambientes distintos a desarrollo (Waitress, compatible con Windows).

    AUTOMATE_ENV=production python serve.py

Host y puerto: variables HOST (por defecto 127.0.0.1) y PORT (por defecto 8000).
Detrás de IIS/Nginx con HTTPS, mantener SESSION_COOKIE_SECURE=1.
"""
import os

from waitress import serve

from app import create_app

if __name__ == "__main__":
    app = create_app()
    serve(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")), threads=8)
