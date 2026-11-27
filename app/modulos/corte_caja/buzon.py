"""Acceso al buzón del robot.

``Buzon`` es el contrato que usa el módulo; ``BuzonEws`` lo implementa con Exchange Web
Services y las pruebas usan un buzón simulado. El contrato vive en el módulo, no en el núcleo:
Contraseñas usa otra plataforma (Microsoft Graph) y no se unifican hasta que TI decida una sola
(principio 5 de docs/ARQUITECTURA.md).

**El buzón es la cola.** Lo que está en la bandeja de entrada está pendiente; al terminar, cada
correo se mueve a una subcarpeta (``Procesados``, ``Rechazados``, ``Ignorados``, ``Error``). Así
no hay marca de agua que pueda saltarse un correo que falló.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

CARPETA_PROCESADOS = "Procesados"
CARPETA_SIN_MOVIMIENTO = "Sin movimiento"
CARPETA_RECHAZADOS = "Rechazados"
CARPETA_IGNORADOS = "Ignorados"
CARPETA_ERROR = "Error"
CARPETAS = (CARPETA_PROCESADOS, CARPETA_SIN_MOVIMIENTO, CARPETA_RECHAZADOS, CARPETA_IGNORADOS, CARPETA_ERROR)


class BuzonNoDisponible(RuntimeError):
    """No se pudo conectar al buzón (credenciales, red o servidor)."""


@dataclass(frozen=True)
class Adjunto:
    nombre: str
    contenido: bytes


@dataclass(frozen=True)
class Correo:
    id: str                      # identificador del proveedor, para responder y mover
    message_id: str              # Message-ID de internet (estable entre carpetas)
    asunto: str
    remitente: str               # dirección SMTP
    recibido: datetime           # UTC sin zona
    encabezados: dict[str, str] = field(default_factory=dict)   # nombres en minúsculas
    adjuntos: tuple[Adjunto, ...] = ()
    cuerpo: str = ""             # texto del mensaje (puede traer HTML); se usa para «sin movimiento»


class Buzon(Protocol):
    def pendientes(self, limite: int, desde: datetime | None = None) -> list[Correo]:
        """Correos de la bandeja de entrada, del más antiguo al más reciente."""

    def responder(self, correo: Correo, asunto: str, html: str) -> None:
        """Responde solo al remitente (nunca a todos)."""

    def mover(self, correo: Correo, carpeta: str) -> None:
        """Mueve el correo a una subcarpeta de la bandeja de entrada (la crea si no existe)."""


def _usar_proxy(proxy: str) -> None:
    """Envía el tráfico de exchangelib por un proxy HTTP.

    Desde la red interna, ``owa.canella.com.gt`` resuelve a la IP pública y solo es alcanzable a
    través del proxy corporativo (como hace el navegador). Es el mecanismo que documenta
    exchangelib: un adaptador HTTP propio. Afecta solo a exchangelib, que en el hub usa únicamente
    este módulo."""
    import requests
    from exchangelib.protocol import BaseProtocol

    proxies = {"http": proxy, "https": proxy}

    class AdaptadorConProxy(requests.adapters.HTTPAdapter):
        def send(self, *args, **kwargs):
            kwargs["proxies"] = proxies
            return super().send(*args, **kwargs)

    BaseProtocol.HTTP_ADAPTER_CLS = AdaptadorConProxy


class BuzonEws:
    """Buzón en Exchange (OWA de Canella) con usuario y contraseña, igual que el prototipo."""

    def __init__(self, servidor: str, usuario: str, contrasena: str, direccion: str, proxy: str | None = None) -> None:
        # Import diferido: exchangelib solo se instala con requirements-corte_caja.txt, y el hub
        # (y sus pruebas) deben poder cargar el módulo sin ella.
        import exchangelib

        self._ews = exchangelib
        if proxy:
            _usar_proxy(proxy)
        try:
            credenciales = exchangelib.Credentials(usuario, contrasena)
            configuracion = exchangelib.Configuration(server=servidor, credentials=credenciales)
            self._cuenta = exchangelib.Account(
                primary_smtp_address=direccion, config=configuracion,
                autodiscover=False, access_type=exchangelib.DELEGATE,
            )
        except Exception as exc:  # errores de red y de autenticación de exchangelib
            raise BuzonNoDisponible(f"No se pudo conectar al buzón {direccion}: {type(exc).__name__}") from exc
        self._mensajes: dict[str, object] = {}
        self._carpetas: dict[str, object] = {}

    def pendientes(self, limite: int, desde: datetime | None = None) -> list[Correo]:
        consulta = self._cuenta.inbox.all()
        if desde is not None:
            zona = self._ews.EWSTimeZone("UTC")
            consulta = consulta.filter(datetime_received__gte=self._ews.EWSDateTime.from_datetime(desde.replace(tzinfo=zona)))
        correos = []
        for mensaje in consulta.order_by("datetime_received")[:limite]:
            if not isinstance(mensaje, self._ews.Message):
                continue  # citas, avisos de lectura y otros elementos que no son correo
            self._mensajes[mensaje.id] = mensaje
            correos.append(self._a_correo(mensaje))
        return correos

    def responder(self, correo: Correo, asunto: str, html: str) -> None:
        self._mensajes[correo.id].reply(subject=asunto, body=self._ews.HTMLBody(html))

    def mover(self, correo: Correo, carpeta: str) -> None:
        self._mensajes.pop(correo.id).move(self._carpeta(carpeta))

    # ------------------------------------------------------------------ detalle de EWS

    def _carpeta(self, nombre: str):
        if nombre not in self._carpetas:
            bandeja = self._cuenta.inbox
            existente = next((c for c in bandeja.children if c.name == nombre), None)
            if existente is None:
                existente = self._ews.Folder(parent=bandeja, name=nombre)
                existente.save()
            self._carpetas[nombre] = existente
        return self._carpetas[nombre]

    def _smtp(self, buzon) -> str:
        """Dirección SMTP del remitente. Los remitentes internos de Exchange pueden venir como
        dirección X.500 (``routing_type == "EX"``): se resuelven contra el directorio."""
        if buzon is None:
            return ""
        direccion = buzon.email_address or ""
        if getattr(buzon, "routing_type", "SMTP") == "EX" or "@" not in direccion:
            try:
                for resuelto in self._cuenta.protocol.resolve_names([direccion]):
                    if getattr(resuelto, "email_address", None) and "@" in resuelto.email_address:
                        return resuelto.email_address.lower()
            except Exception:
                return ""
            return ""
        return direccion.lower()

    def _a_correo(self, mensaje) -> Correo:
        encabezados = {h.name.lower(): h.value or "" for h in (mensaje.headers or [])}
        adjuntos = tuple(
            Adjunto(nombre=a.name or "", contenido=a.content or b"")
            for a in (mensaje.attachments or [])
            if isinstance(a, self._ews.FileAttachment)
        )
        recibido = mensaje.datetime_received.astimezone(self._ews.EWSTimeZone("UTC")).replace(tzinfo=None)
        return Correo(
            id=mensaje.id,
            message_id=(mensaje.message_id or mensaje.id)[:400],
            asunto=mensaje.subject or "",
            remitente=self._smtp(mensaje.sender or mensaje.author),
            recibido=recibido,
            encabezados=encabezados,
            adjuntos=adjuntos,
            # text_body (Exchange 2013 o posterior) ya viene sin HTML; si no está, el cuerpo tal cual.
            cuerpo=str(getattr(mensaje, "text_body", None) or mensaje.body or ""),
        )
