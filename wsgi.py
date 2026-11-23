"""Punto de entrada WSGI y para la CLI de Flask (``flask --app wsgi ...``)."""
from app import create_app

app = create_app()
