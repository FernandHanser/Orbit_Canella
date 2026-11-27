"""Tablas del módulo (prefijo ``CORTE_CAJA_``).

Reemplazan a los JSON del prototipo: ``correos_procesados.json`` y ``rejected_logs.json`` →
``CORTE_CAJA_CORREOS``; ``transfer_logs.json`` → ``CORTE_CAJA_ARCHIVOS``; la lista fija de
``extract_company`` → ``CORTE_CAJA_EMPRESAS``. No hay tabla de marca de agua: el buzón es la
cola (ver ``buzon.py``). La historia no se recorta a 30 días.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db

from .reglas import PLANTILLA_ESTANDAR


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Empresa(db.Model):
    """Carpeta de destino, subcarpetas por fecha y palabras clave con que se reconoce en el asunto."""

    __tablename__ = "CORTE_CAJA_EMPRESAS"

    id = db.Column(db.Integer, primary_key=True)
    carpeta = db.Column(db.String(100), nullable=False, unique=True)
    palabras_clave = db.Column(db.String(500), nullable=False)   # separadas por coma
    orden = db.Column(db.Integer, nullable=False, default=100)    # la primera que coincide gana
    activa = db.Column(db.Boolean, nullable=False, default=True)
    # Subcarpetas bajo ``carpeta`` (ver reglas.PLANTILLA_ESTANDAR): cada empresa tiene la suya en producción.
    plantilla_carpeta = db.Column(db.String(200), nullable=False, default=PLANTILLA_ESTANDAR,
                                  server_default=PLANTILLA_ESTANDAR)

    @property
    def lista_claves(self) -> tuple[str, ...]:
        return tuple(c.strip() for c in self.palabras_clave.split(",") if c.strip())


class Correo(db.Model):
    """Cada correo tomado del buzón y qué se hizo con él. Un correo devuelto a la bandeja de
    entrada para reintentarlo genera otra fila (por eso ``message_id`` no es único)."""

    __tablename__ = "CORTE_CAJA_CORREOS"

    PROCESADO = "procesado"
    SIN_MOVIMIENTO = "sin_movimiento"   # la caja avisó que no tuvo movimiento: no hay archivos que guardar
    RECHAZADO = "rechazado"
    IGNORADO = "ignorado"
    ERROR = "error"
    ESTADOS = (PROCESADO, SIN_MOVIMIENTO, RECHAZADO, IGNORADO, ERROR)

    id = db.Column(db.Integer, primary_key=True)
    ejecucion_id = db.Column(db.String(32), nullable=False, index=True)
    message_id = db.Column(db.String(400), nullable=False, index=True)
    asunto = db.Column(db.String(500), nullable=False, default="")
    remitente = db.Column(db.String(320), nullable=False, default="")
    recibido = db.Column(db.DateTime, nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, index=True)
    motivo = db.Column(db.Text, nullable=True)
    empresa = db.Column(db.String(100), nullable=True, index=True)
    fecha_corte = db.Column(db.Date, nullable=True)
    # Filas del modo simulación (retirado el 27/11/2026): lo que se habría hecho, sin responder,
    # guardar ni mover. Se conservan en la base pero el tablero no las muestra.
    simulado = db.Column(db.Boolean, nullable=False, default=False)
    # Nombres de todos los adjuntos tal como llegaron, uno por línea (también los de los rechazados).
    adjuntos = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=_ahora_utc, index=True)

    @property
    def lista_adjuntos(self) -> list[str]:
        return [n for n in (self.adjuntos or "").split("\n") if n]

    archivos = db.relationship("Archivo", back_populates="correo", cascade="all, delete-orphan", order_by="Archivo.id")


class Caja(db.Model):
    """Directorio de cajas y tiendas: contra él se arma el cuadre mensual (qué caja envió su corte,
    cuál avisó «sin movimiento» y cuál falta) y se identifica la caja de un rechazo."""

    __tablename__ = "CORTE_CAJA_CAJAS"

    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(100), nullable=False, index=True)
    nombre_caja = db.Column(db.String(150), nullable=False)
    responsable = db.Column(db.String(150), nullable=True)
    # Uno o varios correos separados por coma, punto y coma, barra o espacio.
    correo = db.Column(db.String(500), nullable=True)


class Archivo(db.Model):
    __tablename__ = "CORTE_CAJA_ARCHIVOS"

    id = db.Column(db.Integer, primary_key=True)
    correo_id = db.Column(db.Integer, db.ForeignKey("CORTE_CAJA_CORREOS.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre_original = db.Column(db.String(255), nullable=False)
    nombre_final = db.Column(db.String(255), nullable=False)
    carpeta = db.Column(db.String(500), nullable=False)   # relativa a CORTE_CAJA_DESTINO
    sha256 = db.Column(db.String(64), nullable=False)
    tamano = db.Column(db.Integer, nullable=False)
    duplicado = db.Column(db.Boolean, nullable=False, default=False)

    correo = db.relationship("Correo", back_populates="archivos")
