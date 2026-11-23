"""Tablas del módulo (prefijo ``EXPEDIENTES_SEGUROS_``).

* ``ASEGURADORAS`` + ``CODIGOS``: una aseguradora con uno o varios códigos de socio de SAP sin
  duplicar su configuración (RF-01; MAPFRE y La Ceiba tienen dos).
* ``PARAMETROS``: destinatarios y textos por defecto del correo. Una aseguradora solo guarda lo
  que cambia; si deja un campo vacío, usa el de aquí (así un cambio en Cobros es un solo lugar).
* ``DOCUMENTOS``: checklist de Créditos por aseguradora (qué debe llevar el paquete).
* ``PAQUETES``: registro de cada paquete armado (RF-07): quién, cuándo, qué páginas, a quién.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Aseguradora(db.Model):
    __tablename__ = "EXPEDIENTES_SEGUROS_ASEGURADORAS"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, unique=True)   # nombre corto: MAPFRE, CEIBA…
    # Vacíos = usar los parámetros por defecto del módulo.
    para = db.Column(db.String(1000), nullable=True)
    cc = db.Column(db.String(1000), nullable=True)
    asunto = db.Column(db.String(300), nullable=True)
    cuerpo = db.Column(db.Text, nullable=True)
    activa = db.Column(db.Boolean, nullable=False, default=True)

    codigos = db.relationship("CodigoAseguradora", back_populates="aseguradora", cascade="all, delete-orphan",
                              order_by="CodigoAseguradora.codigo")
    documentos = db.relationship("Documento", back_populates="aseguradora", cascade="all, delete-orphan",
                                 order_by="Documento.orden")

    @property
    def lista_codigos(self) -> str:
        return ", ".join(c.codigo for c in self.codigos)

    @property
    def factura_separada(self) -> bool:
        """Si la factura que Caja sube va en archivo aparte: lo decide la fila «Factura
        original» del checklist, el mismo interruptor «archivo aparte» de cualquier documento
        (antes era una columna propia de la aseguradora; una sola fuente de verdad, no dos)."""
        from . import reglas   # import diferido: reglas.py no depende de models.py, pero evita
                                # cualquier ciclo si algún día sí lo hiciera
        doc = next((d for d in self.documentos if reglas.es_factura(d.nombre)), None)
        return bool(doc and doc.separado)


class CodigoAseguradora(db.Model):
    __tablename__ = "EXPEDIENTES_SEGUROS_CODIGOS"

    codigo = db.Column(db.String(20), primary_key=True)          # OSCL.customer, p. ej. C000078
    aseguradora_id = db.Column(db.Integer, db.ForeignKey("EXPEDIENTES_SEGUROS_ASEGURADORAS.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    aseguradora = db.relationship("Aseguradora", back_populates="codigos")


class Documento(db.Model):
    """Documento del checklist de Créditos para una aseguradora (fuente: checklist por aseguradora).
    ``obligatorio = False`` son los «si aplica»: se muestran, pero no se exigen."""

    __tablename__ = "EXPEDIENTES_SEGUROS_DOCUMENTOS"

    id = db.Column(db.Integer, primary_key=True)
    aseguradora_id = db.Column(db.Integer, db.ForeignKey("EXPEDIENTES_SEGUROS_ASEGURADORAS.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    orden = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    obligatorio = db.Column(db.Boolean, nullable=False, default=True)
    # Inactivo: no se muestra en el visor, pero se conserva para reactivarlo.
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("1"))
    # Sí: este documento sale como su propio PDF, aparte del expediente principal (p. ej. la
    # factura para MAPFRE o El Roble). No (por defecto): sus páginas van unidas en el único PDF.
    separado = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    aseguradora = db.relationship("Aseguradora", back_populates="documentos")


class Parametro(db.Model):
    __tablename__ = "EXPEDIENTES_SEGUROS_PARAMETROS"

    clave = db.Column(db.String(50), primary_key=True)           # para, cc, asunto, cuerpo
    valor = db.Column(db.Text, nullable=False, default="")


class Paquete(db.Model):
    __tablename__ = "EXPEDIENTES_SEGUROS_PAQUETES"

    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, nullable=False, index=True)
    orden = db.Column(db.Integer, nullable=True)
    ceco = db.Column(db.String(20), nullable=True)
    aseguradora_codigo = db.Column(db.String(20), nullable=True)
    aseguradora_nombre = db.Column(db.String(150), nullable=False, default="")
    reclamo = db.Column(db.String(60), nullable=True)
    poliza = db.Column(db.String(60), nullable=True)
    factura_serie = db.Column(db.String(60), nullable=True)
    factura_numero = db.Column(db.String(60), nullable=True)
    anexo = db.Column(db.String(500), nullable=False)             # ruta del original en SAP (solo lectura)
    anexo_sha256 = db.Column(db.String(64), nullable=False)
    # DPI a color de la llamada (segundo anexo en SAP, ver reglas.es_dpi): solo si la llamada lo trae.
    anexo_dpi = db.Column(db.String(500), nullable=True)
    anexo_dpi_sha256 = db.Column(db.String(64), nullable=True)
    paginas = db.Column(db.String(1000), nullable=False)          # "1-3, 7, 9-10"
    cantidad_paginas = db.Column(db.Integer, nullable=False)
    total_paginas = db.Column(db.Integer, nullable=False)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    factura_separada = db.Column(db.Boolean, nullable=False, default=False)
    con_factura = db.Column(db.Boolean, nullable=False, default=False)
    para = db.Column(db.String(1000), nullable=False, default="")
    cc = db.Column(db.String(1000), nullable=False, default="")
    asunto = db.Column(db.String(300), nullable=False, default="")
    # Checklist al generar (JSON): documento, obligatorio, páginas donde está, si estaba presente.
    # Se guardan los nombres, no los ids: editar el checklist después no altera la evidencia.
    checklist = db.Column(db.Text, nullable=True)
    # Tiempo desde que se abrió el visor hasta generar: para comparar con el proceso actual
    # (la ficha exige medir antes de reemplazar el escaneo directo a correo).
    segundos_armado = db.Column(db.Integer, nullable=True)
    usuario_id = db.Column(db.Integer, nullable=True, index=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=_ahora_utc, index=True)
    # Envío desde el buzón del hub (vacío si se descargó el .eml y se envió desde Outlook).
    enviado_en = db.Column(db.DateTime, nullable=True)
    enviado_por = db.Column(db.Integer, nullable=True)
