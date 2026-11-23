"""Reglas de negocio del corte de caja. Funciones puras: sin Flask, sin base de datos, sin red.

Se conservan las reglas afinadas en el prototipo (palabras clave tolerantes a errores de
escritura, periodo de gracia de 45 días, el caso ``MORIO2``) y se corrigen sus defectos: la
fecha debe existir y no ser futura, la empresa no se asume, y los adjuntos se validan igual
sin importar su origen. Ver docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePosixPath
from typing import Mapping, Sequence

MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
PALABRAS_CLAVE = ("corte", "cuadre", "caja", "cort", "cuadr", "cadre", "crte")
EXTENSIONES_PERMITIDAS = (".pdf", ".xls", ".xlsx", ".xlsm")
# Imágenes de firmas y logos incrustados: se ignoran sin contarlas como error.
EXTENSIONES_IGNORADAS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg")
DIAS_GRACIA_ANIO_ANTERIOR = 45
LARGO_MAXIMO_NOMBRE = 150

_FECHA_SEPARADA = re.compile(r"(?<!\d)(\d{2})[/\-.](\d{2})[/\-.](\d{4}|\d{2})(?!\d)")
_FECHA_8_DIGITOS = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)")
_FECHA_6_DIGITOS = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)")
_CARACTERES_INVALIDOS = re.compile(r'[\\/*?:"<>|\x00-\x1f]')
_NOMBRES_RESERVADOS = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
_REMITENTES_AUTOMATICOS = ("mailer-daemon", "postmaster", "no-reply", "noreply", "microsoftexchange")


@dataclass(frozen=True)
class Error:
    """Motivo de rechazo, en texto plano (la plantilla del correo lo escapa)."""

    titulo: str
    detalle: str

    def __str__(self) -> str:
        return f"{self.titulo}: {self.detalle}"


@dataclass(frozen=True)
class Empresa:
    carpeta: str
    palabras_clave: tuple[str, ...]


@dataclass(frozen=True)
class Clasificacion:
    """Resultado de validar un correo: si ``errores`` está vacío, se archiva."""

    fecha: date | None
    empresa: str | None
    adjuntos_validos: tuple[str, ...]
    errores: tuple[Error, ...] = field(default_factory=tuple)

    @property
    def valida(self) -> bool:
        return not self.errores


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes, con la puntuación convertida en espacios simples."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sin_tildes.lower()).split())


# ------------------------------------------------------------------------------------ asunto

def _texto_fecha(asunto: str) -> tuple[str, str, str] | None:
    """Primera fecha con forma DD/MM/AAAA, DD-MM-AA, DDMMAAAA o DDMMAA. Los dígitos pegados a
    otros no cuentan (``MORIO2 24/09/2026`` no se confunde con la fecha)."""
    for patron in (_FECHA_SEPARADA, _FECHA_8_DIGITOS, _FECHA_6_DIGITOS):
        coincidencia = patron.search(asunto)
        if coincidencia:
            dia, mes, anio = coincidencia.groups()
            return dia, mes, anio if len(anio) == 4 else f"20{anio}"
    return None


def extraer_fecha(asunto: str | None) -> date | None:
    """Fecha del corte según el asunto, o ``None`` si no hay una o no existe (31/02)."""
    partes = _texto_fecha(asunto or "")
    if partes is None:
        return None
    dia, mes, anio = partes
    try:
        return date(int(anio), int(mes), int(dia))
    except ValueError:
        return None


def validar_fecha(asunto: str, hoy: date) -> tuple[date | None, Error | None]:
    partes = _texto_fecha(asunto)
    if partes is None:
        return None, Error("Error en el asunto", "No se encontró una fecha válida (DD/MM/AAAA) en el asunto.")
    texto = "/".join(partes)
    fecha = extraer_fecha(asunto)
    if fecha is None:
        return None, Error("Error en el asunto", f"La fecha {texto} no existe en el calendario.")
    if fecha > hoy:
        return None, Error("Error en el asunto", f"La fecha {texto} es futura. Verifica que sea correcta.")
    if fecha.year < hoy.year - 1:
        return None, Error("Error en el asunto", f"La fecha {texto} es de un año muy antiguo ({fecha.year}). Solo se acepta el año actual.")
    if fecha.year == hoy.year - 1 and hoy.timetuple().tm_yday > DIAS_GRACIA_ANIO_ANTERIOR:
        return None, Error(
            "Error en el asunto",
            f"Ya expiró el periodo de gracia de {DIAS_GRACIA_ANIO_ANTERIOR} días para procesar cortes del año {fecha.year}.",
        )
    return fecha, None


def tiene_palabra_clave(asunto: str | None) -> bool:
    limpio = normalizar(asunto)
    return any(palabra in limpio for palabra in PALABRAS_CLAVE)


def identificar_empresa(asunto: str | None, empresas: Sequence[Empresa]) -> str | None:
    """Primera empresa (en el orden recibido) cuya palabra clave aparece en el asunto.

    Sin coincidencia devuelve ``None``: el prototipo asumía CANELLA y archivaba en esa carpeta
    los cortes de cualquier empresa que no se nombrara."""
    limpio = f" {normalizar(asunto)} "
    for empresa in empresas:
        for clave in empresa.palabras_clave:
            clave_limpia = normalizar(clave)
            if clave_limpia and clave_limpia in limpio:
                return empresa.carpeta
    return None


# ---------------------------------------------------------------------------------- adjuntos

def extension(nombre: str | None) -> str:
    return PurePosixPath((nombre or "").replace("\\", "/")).suffix.lower()


def es_adjunto_ignorable(nombre: str | None) -> bool:
    return extension(nombre) in EXTENSIONES_IGNORADAS


def validar_nombre_adjunto(nombre: str | None) -> bool:
    """PDF o Excel con al menos tres partes separadas por guion: ``24092026-ABC-Cuadre.pdf``."""
    if not nombre or extension(nombre) not in EXTENSIONES_PERMITIDAS:
        return False
    base = nombre[: -len(extension(nombre))]
    return len(base.split("-")) >= 3


def nombre_seguro(nombre: str) -> str:
    """Nombre de archivo apto para la carpeta compartida: sin separadores ni caracteres
    inválidos en Windows, sin nombres reservados y con largo acotado (conserva la extensión)."""
    limpio = _CARACTERES_INVALIDOS.sub("", nombre).strip().strip(".")
    ext = extension(limpio)
    base = limpio[: -len(ext)] if ext else limpio
    base = base.strip().strip(".")
    if not base or base.lower() in _NOMBRES_RESERVADOS:
        base = f"archivo_{base}" if base else "archivo"
    return base[: LARGO_MAXIMO_NOMBRE - len(ext)] + ext


def carpeta_destino(empresa: str, fecha: date) -> tuple[str, ...]:
    """``Empresa/Año/Mes/DD-MM-AAAA``, la estructura que ya usa Contabilidad."""
    return (empresa, str(fecha.year), MESES[fecha.month - 1], fecha.strftime("%d-%m-%Y"))


# ------------------------------------------------------------------------------- remitente

def dominio(correo: str | None) -> str:
    return (correo or "").rpartition("@")[2].strip().lower()


def remitente_permitido(correo: str | None, dominios: Sequence[str]) -> bool:
    return bool(correo) and dominio(correo) in {d.strip().lower() for d in dominios}


def es_mensaje_automatico(remitente: str | None, encabezados: Mapping[str, str]) -> bool:
    """Respuestas automáticas, rebotes y listas: nunca se les responde (evita bucles entre robots).

    ``encabezados`` con nombres en minúsculas."""
    local = (remitente or "").partition("@")[0].lower()
    if any(local.startswith(prefijo) for prefijo in _REMITENTES_AUTOMATICOS):
        return True
    if encabezados.get("auto-submitted", "no").strip().lower() != "no":
        return True
    if "x-auto-response-suppress" in encabezados or "x-autoreply" in encabezados:
        return True
    return encabezados.get("precedence", "").strip().lower() in {"bulk", "junk", "list", "auto_reply"}


# ------------------------------------------------------------------------------ clasificar

def clasificar(asunto: str | None, adjuntos: Sequence[str], empresas: Sequence[Empresa], hoy: date) -> Clasificacion:
    """Valida asunto y nombres de adjuntos. Reúne todos los errores para explicarlos en un solo
    correo de rechazo."""
    errores: list[Error] = []
    fecha = empresa = None
    if not (asunto or "").strip():
        errores.append(Error("Error en el asunto", "El asunto está vacío."))
    else:
        if not tiene_palabra_clave(asunto):
            errores.append(Error(
                "Error en el asunto",
                "No se detectó ninguna palabra clave válida (ej. 'Corte de Caja', 'Cuadre').",
            ))
        fecha, error_fecha = validar_fecha(asunto, hoy)
        if error_fecha:
            errores.append(error_fecha)
        empresa = identificar_empresa(asunto, empresas)
        if empresa is None:
            nombres = ", ".join(e.carpeta for e in empresas) or "(sin empresas configuradas)"
            errores.append(Error("Error en el asunto", f"No se reconoció la empresa. Empresas válidas: {nombres}."))

    validos: list[str] = []
    for nombre in adjuntos:
        if es_adjunto_ignorable(nombre):
            continue
        if validar_nombre_adjunto(nombre):
            validos.append(nombre)
        else:
            errores.append(Error(
                "Error en archivo adjunto",
                f"El archivo '{nombre}' tiene un nombre o una extensión no válidos (solo PDF o Excel, "
                "con el formato FECHA-EMPRESA-DOCUMENTO).",
            ))
    if not adjuntos:
        errores.append(Error("Error en archivos", "El correo no contiene archivos adjuntos."))
    elif not validos and not any(e.titulo == "Error en archivo adjunto" for e in errores):
        errores.append(Error("Error en archivos", "No se encontró ningún archivo PDF o Excel adjunto."))

    return Clasificacion(fecha=fecha, empresa=empresa, adjuntos_validos=tuple(validos), errores=tuple(errores))
