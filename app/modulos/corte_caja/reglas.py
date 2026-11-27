"""Reglas de negocio del corte de caja. Funciones puras: sin Flask, sin base de datos, sin red.

Se conservan las reglas afinadas en el prototipo (palabras clave tolerantes a errores de
escritura, periodo de gracia de 45 días, el caso ``MORIO2``) y se corrigen sus defectos: la
fecha debe existir y no ser futura, la empresa no se asume, y los adjuntos se validan igual
sin importar su origen. Ver docs/PLAN_INTEGRACION_CORTE_DE_CAJA.md.

Actualizado con lo que el prototipo agregó en producción hasta el 26/11/2026: estructura oficial
de carpetas por empresa, fecha de los archivos igual a la del asunto, adjuntos auxiliares, fecha
rescatada del nombre del archivo y correos «sin movimiento».
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
_FECHA_AL_INICIO = re.compile(r"\s*(\d{2})(\d{2})(\d{4})(?!\d)")

# Subcarpetas bajo la carpeta de la empresa. Fichas: {AAAA} año, {AA} año en dos dígitos,
# {MM} mes en número, {MES} mes en mayúsculas, {Mes} mes capitalizado, {DD} día. La estándar es
# la que usa Contabilidad en producción (Vesa\1.Año 2026\202611NOVIEMBRE\27-11-26).
PLANTILLA_ESTANDAR = "1.Año {AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}"
_FICHA = re.compile(r"\{(AAAA|AA|MM|MES|Mes|DD)\}")


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
    plantilla: str = PLANTILLA_ESTANDAR


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
    error = _error_de_fecha(fecha, texto, hoy)
    return (None, error) if error else (fecha, None)


def _error_de_fecha(fecha: date, texto: str, hoy: date) -> Error | None:
    """Fecha futura, demasiado antigua o del año anterior fuera del periodo de gracia."""
    if fecha > hoy:
        return Error("Error en el asunto", f"La fecha {texto} es futura. Verifica que sea correcta.")
    if fecha.year < hoy.year - 1:
        return Error("Error en el asunto", f"La fecha {texto} es de un año muy antiguo ({fecha.year}). Solo se acepta el año actual.")
    if fecha.year == hoy.year - 1 and hoy.timetuple().tm_yday > DIAS_GRACIA_ANIO_ANTERIOR:
        return Error(
            "Error en el asunto",
            f"Ya expiró el periodo de gracia de {DIAS_GRACIA_ANIO_ANTERIOR} días para procesar cortes del año {fecha.year}.",
        )
    return None


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


def fecha_de_archivo(nombre: str | None) -> tuple[str, date | None] | None:
    """Fecha con que empieza el nombre (``24092026-ABC-Cuadre.pdf``): ``(texto DD/MM/AAAA, fecha)``.

    ``None`` si el nombre no empieza con 8 dígitos (``Anulacion.pdf``); la fecha es ``None`` si
    los dígitos no forman una fecha que exista."""
    coincidencia = _FECHA_AL_INICIO.match(nombre or "")
    if not coincidencia:
        return None
    dia, mes, anio = coincidencia.groups()
    try:
        fecha = date(int(anio), int(mes), int(dia))
    except ValueError:
        fecha = None
    return f"{dia}/{mes}/{anio}", fecha


def _rellenar(plantilla: str, fecha: date) -> str:
    mes = MESES[fecha.month - 1]
    valores = {
        "AAAA": f"{fecha.year:04d}", "AA": f"{fecha.year % 100:02d}", "MM": f"{fecha.month:02d}",
        "MES": mes.upper(), "Mes": mes, "DD": f"{fecha.day:02d}",
    }
    return _FICHA.sub(lambda m: valores[m.group(1)], plantilla)


def validar_plantilla(plantilla: str | None) -> str | None:
    """Mensaje de error si la plantilla de subcarpetas no sirve, o ``None`` si es válida."""
    plantilla = (plantilla or "").strip()
    if not plantilla:
        return "Indica la estructura de subcarpetas."
    sobrantes = _FICHA.sub("", plantilla)
    if "{" in sobrantes or "}" in sobrantes:
        return "Solo se permiten las fichas {AAAA}, {AA}, {MM}, {MES}, {Mes} y {DD}."
    fichas = set(_FICHA.findall(plantilla))
    if "DD" not in fichas or not fichas & {"MM", "MES", "Mes"} or not fichas & {"AAAA", "AA"}:
        return "Debe incluir el día ({DD}), el mes ({MM}, {MES} o {Mes}) y el año ({AAAA} o {AA})."
    for parte in _rellenar(plantilla, date(2026, 12, 31)).split("/"):
        if not parte or parte != parte.strip() or parte.endswith(".") or parte in (".", ".."):
            return "Cada carpeta (separada por /) debe tener nombre, sin espacios al inicio o al final ni punto al final."
        if _CARACTERES_INVALIDOS.search(parte):
            return 'Las carpetas no pueden llevar los caracteres \\ : * ? " < > |'
    return None


def carpeta_destino(empresa: str, fecha: date, plantilla: str = PLANTILLA_ESTANDAR) -> tuple[str, ...]:
    """Carpeta de la empresa y sus subcarpetas según la plantilla, la estructura oficial que usa
    Contabilidad (``Vesa/1.Año 2026/202611NOVIEMBRE/27-11-26``)."""
    return (empresa, *_rellenar(plantilla, fecha).split("/"))


# --------------------------------------------------------------------------- sin movimiento

# Una negación y una palabra de actividad, con a lo sumo cuatro palabras de relleno conocidas
# entre ellas («no hubo ningún tipo de movimiento», «no se realizaron ventas»). La lista cerrada
# evita los falsos positivos del prototipo («no olvidar revisar las ventas», «corte en 05/10»),
# que hacían pasar como «sin movimiento» un correo al que solo le faltaban los adjuntos.
_ACTIVIDAD = r"(?:movim[a-z]*|movi[a-z]{2,7}|transacci[a-z]*|operaci[a-z]*|ventas?|actividad(?:es)?)"
_RELLENO = (r"(?:hubo|hay|habia|hubieron|tuvo|tuvimos|tenemos|tiene|se|realizo|realizaron|registro|"
            r"registraron|hizo|hicieron|existe|existio|ningun|ninguna|ningunos|algun|alguna|el|la|los|"
            r"las|de|del|dia|hoy|tipo|clase|en|caja)")
_SIN_MOVIMIENTO = re.compile(
    rf"\b(?:sin|no|cero|ningun[oa]?|nada\s+de)\s+(?:{_RELLENO}\s+){{0,4}}{_ACTIVIDAD}\b"
    rf"|\b{_ACTIVIDAD}\s+(?:cero|0|ningun[oa]?|nada)\b"
)
_FRASES_SIN_MOVIMIENTO = (
    "caja cerrada", "sin novedad", "nada que reportar", "corte en cero", "corte a cero",
    "corte en ceros", "caja en cero", "cero ventas", "sin ventas",
)
LARGO_CUERPO_EVALUADO = 500   # el inicio del cuerpo: deja fuera firmas, avisos legales y respuestas citadas


def indica_sin_movimiento(asunto: str | None, cuerpo: str | None = "") -> bool:
    """El asunto o el inicio del cuerpo dicen que la caja no tuvo movimiento (con errores de
    escritura frecuentes: «movimineto», «sin movieminto»)."""
    sin_html = re.sub(r"&[a-z]+;|&#\d+;", " ", re.sub(r"<[^>]+>", " ", cuerpo or "", flags=re.S), flags=re.I)
    texto = f" {normalizar(asunto)} {normalizar(sin_html)[:LARGO_CUERPO_EVALUADO]} "
    # Solo el inicio de palabra: «sin novedad» también cubre «sin novedades».
    return any(f" {frase}" in texto for frase in _FRASES_SIN_MOVIMIENTO) or bool(_SIN_MOVIMIENTO.search(texto))


def es_sin_movimiento(asunto: str | None, cuerpo: str | None, adjuntos: Sequence[str]) -> bool:
    """Correo que avisa que no hubo movimiento y no trae ningún PDF ni Excel: se registra, no se
    rechaza. Si trae archivos de corte, se procesan como cualquier corte."""
    trae_corte = any(extension(n) in EXTENSIONES_PERMITIDAS for n in adjuntos)
    return not trae_corte and indica_sin_movimiento(asunto, cuerpo)


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

def _fecha_rescatada(adjuntos: Sequence[str], hoy: date) -> date | None:
    """Si el asunto no trae una fecha válida, la del primer PDF o Excel cuyo nombre empieza con
    una fecha válida (``24092026-ABC-Cuadre.pdf``), con las mismas reglas que la del asunto."""
    for nombre in adjuntos:
        if extension(nombre) not in EXTENSIONES_PERMITIDAS:
            continue
        encontrada = fecha_de_archivo(nombre)
        if encontrada and encontrada[1] and _error_de_fecha(encontrada[1], encontrada[0], hoy) is None:
            return encontrada[1]
    return None


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
            # Como en el prototipo: si el asunto no trae fecha o la trae mal (año del año pasado,
            # día futuro), se usa la del nombre de los archivos en lugar de rechazar.
            fecha = _fecha_rescatada(adjuntos, hoy)
            if fecha is None:
                errores.append(error_fecha)
        empresa = identificar_empresa(asunto, empresas)
        if empresa is None:
            nombres = ", ".join(e.carpeta for e in empresas) or "(sin empresas configuradas)"
            errores.append(Error("Error en el asunto", f"No se reconoció la empresa. Empresas válidas: {nombres}."))

    # Se guardan todos los PDF y Excel, también los auxiliares sin el formato (``Anulacion.pdf``),
    # siempre que al menos uno tenga el formato FECHA-EMPRESA-DOCUMENTO.
    validos: list[str] = []
    con_formato = False
    for nombre in adjuntos:
        if es_adjunto_ignorable(nombre):
            continue
        if extension(nombre) not in EXTENSIONES_PERMITIDAS:
            errores.append(Error(
                "Error en archivo adjunto",
                f"El archivo '{nombre}' tiene una extensión no permitida (solo PDF o Excel).",
            ))
            continue
        validos.append(nombre)
        con_formato = con_formato or validar_nombre_adjunto(nombre)
    if not adjuntos:
        errores.append(Error("Error en archivos", "El correo no contiene archivos adjuntos."))
    elif validos and not con_formato:
        errores.append(Error(
            "Error en archivos",
            "Ningún archivo tiene el formato FECHA-EMPRESA-DOCUMENTO (ej. 24092026-ABC-Cuadre.pdf).",
        ))
    elif not validos and not any(e.titulo == "Error en archivo adjunto" for e in errores):
        errores.append(Error("Error en archivos", "No se encontró ningún archivo PDF o Excel adjunto."))

    # La fecha con que empieza cada archivo debe ser la del corte. Los que no empiezan con una
    # fecha (auxiliares) no se comparan.
    if fecha is not None:
        distintas = []
        for nombre in validos:
            encontrada = fecha_de_archivo(nombre)
            if encontrada and encontrada[1] != fecha:
                distintas.append(f"'{nombre}' ({encontrada[0]})")
        if distintas:
            errores.append(Error(
                "Error en fechas",
                f"La fecha del corte ({fecha:%d/%m/%Y}) no coincide con la de: {', '.join(distintas)}. "
                "Verifica las fechas del asunto y de los archivos y vuelve a enviar el correo.",
            ))

    return Clasificacion(fecha=fecha, empresa=empresa, adjuntos_validos=tuple(validos), errores=tuple(errores))
