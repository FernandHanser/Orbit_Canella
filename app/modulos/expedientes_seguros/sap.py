"""Lectura de la llamada de servicio en SAP Business One (solo lectura).

``RepositorioSap`` es el contrato que usa el módulo; ``SapSql`` lo implementa con consultas
directas a ``SBO_CANELLA`` y las pruebas usan un repositorio simulado. El contrato vive en el
módulo: si otro módulo necesita SAP y cambia por el mismo motivo, se sube a ``core`` +
``integraciones`` (principio 5 de docs/ARQUITECTURA.md).

Dónde está cada dato (confirmado con la llamada 51595):

* Llamada: ``OSCL.callID``; orden: ``OSCL.DocNum``; aseguradora: ``OSCL.customer`` / ``custmrName``.
* Reclamo y póliza: ``OSCL.U_Reclamo`` / ``OSCL.U_Poliza``.
* Centro de costo: ``OSCL.U_CECO`` (nombre en ``OPRC``); 1602 = SERVICIOS AUTO TALLER PINTURA.
* Expediente: anexo(s) PDF de la llamada, ``OSCL.AtcEntry`` → ``ATC1`` (``trgtPath\\FileName.FileExt``,
  carpeta del servidor de archivos 128.1.200.122). Puede traer un segundo anexo con el DPI a color
  (mismo ``AbsEntry``, otra ``Line``, nombre empezando en «DPI»: confirmado en ``ATC1`` real); no
  reemplaza el expediente, el módulo los combina (ver ``servicios.bloques_de`` y ``reglas.es_dpi``).
* Bandeja: llamadas **activas** del centro de costo (``OSCL.status <> -1``; -1 = cerrada en SAP B1)
  que **tienen expediente PDF** en sus anexos, sin ventana de días.
* Factura: en Canella se factura **desde la entrega**: ``SCL4`` (``Object = 15``) → ``INV1``
  (``BaseType = 15``) → ``OINV`` (mismo camino que el Tablero de Facturación). También se acepta la
  factura ligada directo (``Object = 13``). Se descartan anuladas y se sugiere la de la aseguradora
  (``CardCode = OSCL.customer``): una llamada de seguro puede tener además la del deducible.
  Serie y Número FEL en campos configurables (``EXPEDIENTES_SAP_CAMPO_SERIE`` / ``_NUMERO``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PureWindowsPath
from typing import Protocol

from .configuracion import ConfigSap


class SapNoDisponible(RuntimeError):
    """No se pudo consultar SAP (red, credenciales o servidor)."""


@dataclass(frozen=True)
class Anexo:
    linea: int
    ruta: str              # ruta completa del archivo en el servidor de archivos
    nombre: str            # nombre con extensión, para mostrar
    fecha: datetime | None


@dataclass(frozen=True)
class Factura:
    doc_num: int
    serie: str
    numero: str
    fecha: date | None = None
    cliente: str = ""               # OINV.CardName
    de_aseguradora: bool = True     # CardCode = OSCL.customer (la otra suele ser el deducible)


@dataclass(frozen=True)
class Llamada:
    call_id: int
    orden: int                     # OSCL.DocNum
    aseguradora_codigo: str        # OSCL.customer (C000078)
    aseguradora_nombre: str        # OSCL.custmrName
    reclamo: str
    poliza: str
    ceco: str
    ceco_nombre: str
    anexos: tuple[Anexo, ...]      # solo PDF, en el orden de SAP
    factura: Factura | None        # la sugerida: la más reciente de la aseguradora
    facturas: tuple[Factura, ...] = ()   # todas las de la llamada, sin anuladas


@dataclass(frozen=True)
class Pendiente:
    """Fila de la bandeja: llamada activa del centro de costo con expediente PDF."""

    call_id: int
    aseguradora_codigo: str
    aseguradora_nombre: str
    reclamo: str
    creada: date                # OSCL.createDate: la antigüedad se cuenta desde aquí
    expediente: date            # fecha del anexo PDF más reciente


class RepositorioSap(Protocol):
    def buscar_llamada(self, call_id: int) -> Llamada | None:
        """La llamada con sus anexos PDF y su factura, o ``None`` si no existe."""

    def pendientes(self, ceco: str) -> list[Pendiente]:
        """Llamadas activas (no cerradas) del centro de costo con expediente PDF, de la más antigua a
        la más reciente."""


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _fecha(valor) -> date | None:
    return valor.date() if isinstance(valor, datetime) else valor


class SapSql:
    """Consultas de solo lectura a SBO_CANELLA con pyodbc."""

    def __init__(self, config: ConfigSap) -> None:
        self._config = config

    def _conectar(self):
        import pyodbc  # dependencia del hub (requirements.txt)

        c = self._config
        try:
            return pyodbc.connect(
                f"DRIVER={{{c.driver}}};SERVER={c.servidor};DATABASE={c.base};UID={c.usuario};PWD={c.contrasena};"
                "ApplicationIntent=ReadOnly",
                timeout=10, readonly=True,
            )
        except pyodbc.Error as exc:
            raise SapNoDisponible(f"No se pudo conectar a SAP ({c.servidor}/{c.base}): {type(exc).__name__}") from exc

    def buscar_llamada(self, call_id: int) -> Llamada | None:
        c = self._config
        conexion = self._conectar()
        try:
            cur = conexion.cursor()
            fila = cur.execute(
                """
                SELECT S.callID, S.DocNum, S.customer, S.custmrName, S.U_Reclamo, S.U_Poliza,
                       S.U_CECO, P.PrcName, S.AtcEntry
                FROM OSCL S LEFT JOIN OPRC P ON P.PrcCode = S.U_CECO
                WHERE S.callID = ?
                """, call_id,
            ).fetchone()
            if fila is None:
                return None
            anexos = ()
            if fila.AtcEntry:
                anexos = tuple(
                    Anexo(
                        linea=a.Line,
                        ruta=str(PureWindowsPath(_texto(a.trgtPath)) / f"{_texto(a.FileName)}.{_texto(a.FileExt)}"),
                        nombre=f"{_texto(a.FileName)}.{_texto(a.FileExt).lower()}",
                        fecha=a.Date,
                    )
                    for a in cur.execute(
                        "SELECT Line, trgtPath, FileName, FileExt, Date FROM ATC1 "
                        "WHERE AbsEntry = ? AND UPPER(FileExt) = 'PDF' ORDER BY Line", fila.AtcEntry,
                    ).fetchall()
                )
            # Nombres de columna validados en configuracion._identificador.
            filas = cur.execute(
                f"""
                SELECT I.DocEntry, I.DocNum, I.DocDate, I.CardCode, I.CardName,
                       I.[{c.campo_serie}] AS Serie, I.[{c.campo_numero}] AS Numero
                FROM OINV I
                WHERE I.CANCELED = 'N' AND I.DocEntry IN (
                    SELECT R.DocEntry FROM SCL4 L
                    JOIN INV1 R ON R.BaseType = 15 AND R.BaseEntry = L.DocAbs
                    WHERE L.SrcvCallID = ? AND L.Object = '15'
                    UNION
                    SELECT L.DocAbs FROM SCL4 L WHERE L.SrcvCallID = ? AND L.Object = '13')
                ORDER BY I.DocDate DESC, I.DocEntry DESC
                """, call_id, call_id,
            ).fetchall()
            aseguradora = _texto(fila.customer)
            facturas = tuple(
                Factura(int(f.DocNum), _texto(f.Serie), _texto(f.Numero),
                        f.DocDate.date() if isinstance(f.DocDate, datetime) else f.DocDate,
                        _texto(f.CardName), _texto(f.CardCode) == aseguradora)
                for f in filas
            )
            return Llamada(
                call_id=int(fila.callID), orden=int(fila.DocNum or 0),
                aseguradora_codigo=aseguradora, aseguradora_nombre=_texto(fila.custmrName),
                reclamo=_texto(fila.U_Reclamo), poliza=_texto(fila.U_Poliza),
                ceco=_texto(fila.U_CECO), ceco_nombre=_texto(fila.PrcName),
                anexos=anexos, factura=next((f for f in facturas if f.de_aseguradora), None), facturas=facturas,
            )
        except SapNoDisponible:
            raise
        except Exception as exc:
            raise SapNoDisponible(f"Error al consultar SAP: {type(exc).__name__}: {exc}") from exc
        finally:
            conexion.close()

    def pendientes(self, ceco: str) -> list[Pendiente]:
        conexion = self._conectar()
        try:
            filas = conexion.cursor().execute(
                """
                SELECT S.callID, S.customer, S.custmrName, S.U_Reclamo, S.createDate, MAX(A.Date) AS Expediente
                FROM OSCL S
                JOIN ATC1 A ON A.AbsEntry = S.AtcEntry AND UPPER(A.FileExt) = 'PDF'
                WHERE S.U_CECO = ? AND S.status <> -1
                GROUP BY S.callID, S.customer, S.custmrName, S.U_Reclamo, S.createDate
                ORDER BY S.createDate, S.callID
                """, ceco,
            ).fetchall()
            return [
                Pendiente(int(f.callID), _texto(f.customer), _texto(f.custmrName), _texto(f.U_Reclamo),
                          _fecha(f.createDate), _fecha(f.Expediente))
                for f in filas
            ]
        except Exception as exc:
            raise SapNoDisponible(f"Error al consultar la bandeja en SAP: {type(exc).__name__}: {exc}") from exc
        finally:
            conexion.close()
