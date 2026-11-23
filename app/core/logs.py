"""Sistema central de logs de ORBIT Canella.

Todos los eventos (hub y módulos) usan la misma configuración:

* Un logger por módulo: ``get_logger("<id_modulo>")`` → ``automate.<id_modulo>``.
  Los eventos del hub usan ``get_logger("core")``.
* Cada registro lleva: fecha y hora, nivel, módulo, evento, mensaje, usuario,
  identificador de ejecución y, si hubo excepción, la traza completa.
* Salida a archivo en formato JSON Lines (``logs/automate-AAAA-MM-DD.jsonl``), un
  archivo por día y retención configurable por ambiente; salida legible a consola.
* Los mensajes se sanean: se ocultan valores de contraseñas, tokens y secretos y se
  recorta el texto largo para no volcar documentos completos.

Uso desde un módulo::

    from app.core.logs import get_logger
    log = get_logger("mi_modulo")
    log.info("Archivo recibido", extra={"evento": "archivo.recibido", "datos": {"nombre": nombre}})
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

RAIZ = "automate"
MODULO_CORE = "core"
MAX_MENSAJE = 2000
MAX_VALOR_DATO = 300
PREFIJO_ARCHIVO = "automate"

_ejecucion_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("ejecucion_id", default=None)
_usuario_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("usuario_log", default=None)

NIVELES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def get_logger(modulo_id: str = MODULO_CORE) -> logging.Logger:
    """Devuelve el logger común para un módulo (o ``core`` para el hub)."""
    return logging.getLogger(f"{RAIZ}.{modulo_id}")


# --------------------------------------------------------------------------- contexto

def establecer_ejecucion(ejecucion_id: str | None) -> contextvars.Token:
    return _ejecucion_ctx.set(ejecucion_id)


def restablecer_ejecucion(token: contextvars.Token) -> None:
    _ejecucion_ctx.reset(token)


def establecer_usuario(usuario: str | None) -> contextvars.Token:
    """Identidad para logs fuera de una petición web (p. ej. ``proceso:cierre_nocturno``)."""
    return _usuario_ctx.set(usuario)


def restablecer_usuario(token: contextvars.Token) -> None:
    _usuario_ctx.reset(token)



def _usuario_actual() -> str | None:
    explicito = _usuario_ctx.get()
    if explicito:
        return explicito
    try:
        from flask import g, has_request_context

        if has_request_context():
            # Se lee el usuario ya cargado por Flask-Login sin disparar una nueva carga.
            usuario = getattr(g, "_login_user", None)
            if usuario is not None and getattr(usuario, "is_authenticated", False):
                return usuario.usuario_stod
    except Exception:  # pragma: no cover - el logging nunca debe romper la app
        pass
    return None


def _modulo_desde_registro(record: logging.LogRecord) -> str:
    partes = record.name.split(".")
    if partes[0] == RAIZ and len(partes) > 1:
        return partes[1]
    # Loggers externos (Flask, Werkzeug...): se atribuyen al módulo de la petición en curso.
    try:
        from flask import g, has_request_context

        if has_request_context():
            definicion = getattr(g, "modulo_actual", None)
            if definicion is not None:
                return definicion.id
    except Exception:  # pragma: no cover
        pass
    return MODULO_CORE


# --------------------------------------------------------------------------- saneamiento

_CLAVES_SENSIBLES = r"password|passwd|pwd|contrase(?:ñ|n)a|clave|token|secret|secreto|api[_-]?key|authorization|cookie"
_PATRON_SENSIBLE = re.compile(rf"(?i)\b({_CLAVES_SENSIBLES})(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)")
_PATRON_CLAVE = re.compile(rf"(?i)({_CLAVES_SENSIBLES})")


def sanear_texto(texto: str, maximo: int = MAX_MENSAJE) -> str:
    texto = _PATRON_SENSIBLE.sub(r"\1\2***", texto)
    if len(texto) > maximo:
        texto = f"{texto[:maximo]}… [recortado, {len(texto)} caracteres]"
    return texto


def sanear_datos(datos: Any) -> Any:
    if isinstance(datos, dict):
        return {
            str(k): ("***" if _PATRON_CLAVE.search(str(k)) else sanear_datos(v)) for k, v in datos.items()
        }
    if isinstance(datos, (list, tuple)):
        return [sanear_datos(v) for v in list(datos)[:50]]
    if isinstance(datos, (int, float, bool)) or datos is None:
        return datos
    return sanear_texto(str(datos), MAX_VALOR_DATO)


# --------------------------------------------------------------------------- filtros y formatos

class SinAccesosHttpFilter(logging.Filter):
    """Deja fuera del archivo el registro de accesos de werkzeug (una línea por cada CSS, JS o
    imagen). Siguen en la consola; al archivo solo llegan sus advertencias y errores."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.name.startswith("werkzeug") and record.levelno < logging.WARNING)


class ContextoFilter(logging.Filter):
    """Completa cada registro con módulo, usuario, ejecución y evento."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "modulo", None):
            record.modulo = _modulo_desde_registro(record)
        if not getattr(record, "usuario", None):
            record.usuario = _usuario_actual()
        if not getattr(record, "ejecucion_id", None):
            record.ejecucion_id = _ejecucion_ctx.get()
        if not getattr(record, "evento", None):
            record.evento = None
        return True


def _hora_local(record: logging.LogRecord) -> str:
    return datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="milliseconds")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entrada: dict[str, Any] = {
            "ts": _hora_local(record),
            "nivel": record.levelname,
            "modulo": getattr(record, "modulo", MODULO_CORE),
            "evento": getattr(record, "evento", None),
            "mensaje": sanear_texto(record.getMessage()),
            "usuario": getattr(record, "usuario", None),
            "ejecucion_id": getattr(record, "ejecucion_id", None),
            "logger": record.name,
        }
        datos = getattr(record, "datos", None)
        if datos:
            entrada["datos"] = sanear_datos(datos)
        if record.exc_info:
            entrada["traza"] = sanear_texto(self.formatException(record.exc_info), 20000)
        return json.dumps(entrada, ensure_ascii=False, default=str)


class TextoFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        partes = [
            _hora_local(record)[:23].replace("T", " "),
            f"{record.levelname:<8}",
            f"[{getattr(record, 'modulo', MODULO_CORE)}]",
        ]
        if getattr(record, "evento", None):
            partes.append(f"{record.evento}")
        partes.append(sanear_texto(record.getMessage()))
        if getattr(record, "usuario", None):
            partes.append(f"usuario={record.usuario}")
        if getattr(record, "ejecucion_id", None):
            partes.append(f"ejecucion={record.ejecucion_id}")
        linea = " ".join(partes)
        if record.exc_info:
            linea += "\n" + sanear_texto(self.formatException(record.exc_info), 20000)
        return linea


class ArchivoDiarioHandler(logging.Handler):
    """Escribe en ``<dir>/automate-AAAA-MM-DD.jsonl`` y purga archivos vencidos.

    No renombra archivos (a diferencia de TimedRotatingFileHandler), por lo que el
    servidor web y los procesos programados pueden escribir a la vez en Windows.
    """

    def __init__(self, directorio: str | Path, retencion_dias: int):
        super().__init__()
        self.directorio = Path(directorio)
        self.directorio.mkdir(parents=True, exist_ok=True)
        self.retencion_dias = max(retencion_dias, 1)
        self._fecha: date | None = None
        self._stream = None

    def _ruta(self, fecha: date) -> Path:
        return self.directorio / f"{PREFIJO_ARCHIVO}-{fecha:%Y-%m-%d}.jsonl"

    def _abrir(self, hoy: date) -> None:
        if self._stream is not None:
            self._stream.close()
        self._stream = open(self._ruta(hoy), "a", encoding="utf-8")
        self._fecha = hoy
        self._purgar(hoy)

    def _purgar(self, hoy: date) -> None:
        limite = hoy - timedelta(days=self.retencion_dias)
        for archivo in self.directorio.glob(f"{PREFIJO_ARCHIVO}-*.jsonl"):
            try:
                fecha = datetime.strptime(archivo.stem[len(PREFIJO_ARCHIVO) + 1 :], "%Y-%m-%d").date()
            except ValueError:
                continue
            if fecha < limite:
                try:
                    archivo.unlink()
                except OSError:
                    pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            mensaje = self.format(record)
            hoy = date.today()
            if hoy != self._fecha or self._stream is None:
                self._abrir(hoy)
            self._stream.write(mensaje + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self.acquire()
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            self.release()
        super().close()


# --------------------------------------------------------------------------- configuración

def configurar_logging(app) -> None:
    """Instala los handlers comunes. Idempotente (se puede llamar en cada create_app)."""
    raiz = logging.getLogger()
    for handler in list(raiz.handlers):
        if getattr(handler, "_automate", False):
            raiz.removeHandler(handler)
            handler.close()

    nivel = getattr(logging, str(app.config["LOG_LEVEL"]).upper(), logging.INFO)
    filtro = ContextoFilter()

    if app.config.get("LOG_ARCHIVO", True):
        archivo = ArchivoDiarioHandler(app.config["LOG_DIR"], app.config["LOG_RETENCION_DIAS"])
        archivo.setFormatter(JsonFormatter())
        archivo.addFilter(filtro)
        archivo.addFilter(SinAccesosHttpFilter())
        archivo._automate = True
        raiz.addHandler(archivo)

    if app.config.get("LOG_CONSOLA", True):
        consola = logging.StreamHandler(sys.stderr)
        consola.setFormatter(TextoFormatter())
        consola.addFilter(filtro)
        consola._automate = True
        raiz.addHandler(consola)

    # Bibliotecas externas: solo advertencias; los eventos propios según el ambiente.
    raiz.setLevel(logging.WARNING)
    logging.getLogger(RAIZ).setLevel(nivel)
    logging.getLogger("werkzeug").setLevel(logging.INFO)  # accesos visibles en consola, no en archivo
    app.logger.setLevel(nivel)
    app.logger.handlers.clear()
    app.logger.propagate = True


# --------------------------------------------------------------------------- consulta

def _nivel_num(nivel: str | None) -> int:
    return getattr(logging, (nivel or "DEBUG").upper(), logging.DEBUG)


def _leer_inverso(ruta: Path) -> Iterator[str]:
    with open(ruta, "r", encoding="utf-8", errors="replace") as f:
        lineas = f.readlines()
    return reversed(lineas)


def buscar_logs(
    directorio: str | Path,
    modulo: str | None = None,
    ejecucion_id: str | None = None,
    nivel_minimo: str | None = None,
    usuario: str | None = None,
    texto: str | None = None,
    dias: int = 7,
    limite: int = 500,
) -> list[dict[str, Any]]:
    """Busca eventos en los archivos JSONL, del más reciente al más antiguo."""
    directorio = Path(directorio)
    if not directorio.exists():
        return []
    desde = date.today() - timedelta(days=max(dias, 1) - 1)
    archivos = sorted(directorio.glob(f"{PREFIJO_ARCHIVO}-*.jsonl"), reverse=True)
    minimo = _nivel_num(nivel_minimo)
    texto = (texto or "").lower().strip()
    resultados: list[dict[str, Any]] = []
    for archivo in archivos:
        try:
            fecha = datetime.strptime(archivo.stem[len(PREFIJO_ARCHIVO) + 1 :], "%Y-%m-%d").date()
        except ValueError:
            continue
        if fecha < desde:
            continue
        for linea in _leer_inverso(archivo):
            linea = linea.strip()
            if not linea:
                continue
            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if modulo and evento.get("modulo") != modulo:
                continue
            if ejecucion_id and evento.get("ejecucion_id") != ejecucion_id:
                continue
            if usuario and evento.get("usuario") != usuario:
                continue
            if _nivel_num(evento.get("nivel")) < minimo:
                continue
            if texto and texto not in f"{evento.get('mensaje', '')} {evento.get('evento', '')}".lower():
                continue
            resultados.append(evento)
            if len(resultados) >= limite:
                return resultados
    return resultados
