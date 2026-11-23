"""Configuración por ambiente.

El ambiente se elige con la variable ``AUTOMATE_ENV`` (development, testing, production).
Todos los valores sensibles se leen de variables de entorno o del archivo ``.env``
(no versionado). Ver ``.env.example``.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Se carga aquí (y no en create_app) porque las clases de configuración leen el
# entorno al importarse. Las variables ya definidas en el sistema tienen prioridad.
load_dotenv(BASE_DIR / ".env")


def _env(nombre: str, defecto=None):
    """Lee una variable de entorno; vacía equivale a no definida."""
    valor = os.getenv(nombre)
    return defecto if valor is None or not valor.strip() else valor.strip()


def _bool(nombre: str, defecto: bool = False) -> bool:
    valor = _env(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


def _lista(nombre: str) -> list[str] | None:
    valor = _env(nombre)
    if not valor:
        return None
    return [v.strip() for v in valor.split(",") if v.strip()]


class Config:

    SECRET_KEY = _env("SECRET_KEY")

    # Base de datos: SQL Server AUTOMATE_CANELLA (obligatoria; ver scripts/sqlserver/README.md).
    SQLALCHEMY_DATABASE_URI = _env("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # pool_pre_ping: antes de usar una conexión del pool, hace un "SELECT 1" barato; si el otro
    # lado ya la cerró (firewall, VPN, reinicio de SQL Server), la descarta y abre una nueva en
    # vez de fallar la petición con "conexión perdida". pool_recycle: igual, pero por tiempo,
    # más corto que el timeout típico de un firewall (para no llegar a necesitar el ping).
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(_env("DB_POOL_RECYCLE_SEGUNDOS", "280")),
    }

    # Sesiones
    SESSION_COOKIE_NAME = "automate_canella_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    # Inactividad y jornada máxima: las controla app/core/sesion.py. La cookie vive lo que la
    # jornada para que el servidor pueda decir por qué venció (inactividad o jornada).
    SESION_INACTIVIDAD_MINUTOS = float(_env("SESION_INACTIVIDAD_MINUTOS", "60"))
    SESION_MAXIMA_HORAS = float(_env("SESION_MAXIMA_HORAS", "10"))
    SESION_AVISO_SEGUNDOS = int(_env("SESION_AVISO_SEGUNDOS", "120"))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESION_MAXIMA_HORAS)

    # CSRF (Flask-WTF). Aplica a formularios y a peticiones POST/PUT/PATCH/DELETE de la API.
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # el token vive lo que dure la sesión

    # Bloqueo por intentos fallidos de inicio de sesión (lo aplica el hub; no se escribe en STOD)
    LOGIN_MAX_INTENTOS = int(_env("LOGIN_MAX_INTENTOS", "5"))
    LOGIN_BLOQUEO_MINUTOS = int(_env("LOGIN_BLOQUEO_MINUTOS", "15"))

    # Identidad: usuarios de STOD (ASP.NET Membership). Ver app/integraciones/stod.py.
    AUTH_PROVEEDOR = "stod"
    STOD_SERVER = _env("STOD_SERVER")
    STOD_DATABASE = _env("STOD_DATABASE", "STOD_SAPBONE")
    STOD_USERNAME = _env("STOD_USERNAME")
    STOD_PASSWORD = _env("STOD_PASSWORD")
    STOD_ODBC_DRIVER = _env("STOD_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    STOD_TIMEOUT = int(_env("STOD_TIMEOUT", "10"))
    # Cada cuánto se vuelve a comprobar en STOD que un usuario con sesión abierta siga activo.
    STOD_REVALIDAR_MINUTOS = int(_env("STOD_REVALIDAR_MINUTOS", "15"))

    # Ejecuciones: al arrancar, las que siguen "en_curso" tras estas horas se marcan "interrumpida".
    # Debe ser mayor que la duración de la tarea más larga.
    EJECUCIONES_INTERRUMPIDAS_HORAS = float(_env("EJECUCIONES_INTERRUMPIDAS_HORAS", "2"))
    # Días que se conservan las ejecuciones "sin_cambios" (corridas sin nada que procesar).
    EJECUCIONES_SIN_CAMBIOS_DIAS = float(_env("EJECUCIONES_SIN_CAMBIOS_DIAS", "7"))

    # Logs
    LOG_DIR = _env("LOG_DIR", str(BASE_DIR / "logs"))
    LOG_LEVEL = _env("LOG_LEVEL", "INFO")
    LOG_RETENCION_DIAS = int(_env("LOG_RETENCION_DIAS", "90"))
    LOG_CONSOLA = _bool("LOG_CONSOLA", True)
    LOG_ARCHIVO = _bool("LOG_ARCHIVO", True)

    # Módulos: None = descubrir automáticamente todos los paquetes en app/modulos.
    # También puede fijarse una lista separada por comas en AUTOMATE_MODULOS.
    MODULOS = _lista("AUTOMATE_MODULOS")


class DevelopmentConfig(Config):
    LOG_LEVEL = _env("LOG_LEVEL", "DEBUG")
    LOG_RETENCION_DIAS = int(_env("LOG_RETENCION_DIAS", "14"))


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "clave-solo-para-pruebas"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTH_PROVEEDOR = "simulado"
    WTF_CSRF_ENABLED = False
    LOG_CONSOLA = False
    LOG_LEVEL = "DEBUG"
    LOG_RETENCION_DIAS = 1


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    LOG_LEVEL = _env("LOG_LEVEL", "INFO")
    LOG_RETENCION_DIAS = int(_env("LOG_RETENCION_DIAS", "180"))


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
