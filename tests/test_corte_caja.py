"""Módulo corte_caja: reglas, archivador, tarea con buzón simulado, tablero y directorio.

Sin buzón ni carpeta de red reales: ``BuzonFalso`` reemplaza a EWS y el destino es ``tmp_path``.
"""
import json
from datetime import date, datetime

import pytest

from app.core.ejecuciones import ejecutar_tarea
from app.extensions import db
from app.modulos.corte_caja import cuadre, historial, reglas, servicios
from app.modulos.corte_caja.archivador import Archivador
from app.modulos.corte_caja.buzon import Adjunto, Correo
from app.modulos.corte_caja.models import Caja as FilaCaja
from app.modulos.corte_caja.models import Correo as FilaCorreo
from app.modulos.corte_caja.models import Empresa as FilaEmpresa

from .conftest import crear_usuario

HOY = date(2026, 9, 28)
EMPRESAS = [
    reglas.Empresa("MAQUIPOS", ("maquipo",)),
    reglas.Empresa("VESA", ("vesa", "besa")),
    reglas.Empresa("Cobradores", ("colaborador", "cobrador")),
    reglas.Empresa("Mauto", ("mauto", "mantenimiento automotriz")),
    reglas.Empresa("MR. Credit", ("mr credit", "mrcredit", "mister credit")),
    reglas.Empresa("CANELLA", ("canella",)),
]
PDF = "24092026-ABC-Cuadre.pdf"
# Estructura oficial (plantilla estándar) para un corte del 24/09/2026.
DIA_VESA = ("VESA", "1.Año 2026", "202609SEPTIEMBRE", "24-09-26")


# =========================================================================== reglas

@pytest.mark.parametrize("asunto, esperada", [
    ("Corte de caja Canella 24/09/2026", date(2026, 9, 24)),
    ("Corte de caja Canella 24-09-26", date(2026, 9, 24)),
    ("Corte de caja Canella 24.09.2026", date(2026, 9, 24)),
    ("Corte de caja Canella 24092026", date(2026, 9, 24)),
    ("Corte de caja Canella 240926", date(2026, 9, 24)),
    ("Corte MORIO2 24/09/2026", date(2026, 9, 24)),        # sucursal pegada a un número
    ("Corte de caja Canella 31/02/2026", None),             # no existe
    ("Corte de caja Canella sin fecha", None),
])
def test_extraer_fecha(asunto, esperada):
    assert reglas.extraer_fecha(asunto) == esperada


@pytest.mark.parametrize("asunto, hoy, valida", [
    ("Corte 28/09/2026", HOY, True),
    ("Corte 29/09/2026", HOY, False),                        # futura (el prototipo solo revisaba el año)
    ("Corte 15/12/2025", date(2026, 2, 10), True),           # año anterior dentro de los 45 días
    ("Corte 15/12/2025", date(2026, 3, 1), False),           # año anterior fuera de la gracia
    ("Corte 15/12/2024", date(2026, 1, 5), False),           # demasiado antiguo
])
def test_validar_fecha(asunto, hoy, valida):
    fecha, error = reglas.validar_fecha(asunto, hoy)
    assert (error is None) == valida and (fecha is not None) == valida


@pytest.mark.parametrize("asunto, empresa", [
    ("Corte de caja MAQUIPÓS 24/09/2026", "MAQUIPOS"),
    ("cuadre Besa 24/09/2026", "VESA"),
    ("Corte Mr. Credit 24/09/2026", "MR. Credit"),
    ("Corte MR.CREDIT 24/09/2026", "MR. Credit"),
    ("Corte Mantenimiento  Automotriz 24/09/2026", "Mauto"),
    ("Corte Canella zona 1 24/09/2026", "CANELLA"),
    ("Corte de caja 24/09/2026", None),                      # el prototipo asumía CANELLA
])
def test_identificar_empresa(asunto, empresa):
    assert reglas.identificar_empresa(asunto, EMPRESAS) == empresa


@pytest.mark.parametrize("nombre, valido", [
    ("24092026-ABC-Cuadre.pdf", True),
    ("24092026-ABC-Cuadre.XLSM", True),
    ("24092026-ABC.pdf", False),
    ("24092026-ABC-Cuadre.docx", False),
    ("", False),
])
def test_validar_nombre_adjunto(nombre, valido):
    assert reglas.validar_nombre_adjunto(nombre) == valido


def test_nombre_seguro():
    assert reglas.nombre_seguro('..\\..\\a<b>:"c".pdf') == "abc.pdf"
    assert reglas.nombre_seguro("CON.pdf") == "archivo_CON.pdf"
    assert len(reglas.nombre_seguro("x" * 400 + ".pdf")) == reglas.LARGO_MAXIMO_NOMBRE


def test_mensajes_automaticos_y_remitentes():
    assert reglas.es_mensaje_automatico("mailer-daemon@canella.com.gt", {})
    assert reglas.es_mensaje_automatico("ana@canella.com.gt", {"auto-submitted": "auto-replied"})
    assert reglas.es_mensaje_automatico("ana@canella.com.gt", {"x-auto-response-suppress": "All"})
    assert not reglas.es_mensaje_automatico("ana@canella.com.gt", {"auto-submitted": "no"})
    assert reglas.remitente_permitido("Ana@Canella.com.gt", ["canella.com.gt"])
    assert not reglas.remitente_permitido("ana@gmail.com", ["canella.com.gt"])
    assert not reglas.remitente_permitido("", ["canella.com.gt"])


def test_clasificar_reune_todos_los_errores_e_ignora_imagenes():
    c = reglas.clasificar("hola", ["firma.png", "mal.docx"], EMPRESAS, HOY)
    titulos = [e.titulo for e in c.errores]
    assert not c.valida
    assert titulos.count("Error en el asunto") == 3          # palabra clave, fecha, empresa
    assert "Error en archivo adjunto" in titulos
    ok = reglas.clasificar("Corte de caja VESA 24/09/2026", ["firma.png", PDF], EMPRESAS, HOY)
    assert ok.valida and ok.adjuntos_validos == (PDF,) and ok.empresa == "VESA"


@pytest.mark.parametrize("plantilla, esperada", [
    # Las tres estructuras oficiales de producción (prototipo, commit 083118e).
    (reglas.PLANTILLA_ESTANDAR, ("Vesa", "1.Año 2026", "202609SEPTIEMBRE", "04-09-26")),
    ("1.Año{AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}", ("Vesa", "1.Año2026", "202609SEPTIEMBRE", "04-09-26")),   # Canella
    ("1.Año{AAAA}/{MM} {MES} {AAAA}/{DD}-{MM}-{AA}", ("Vesa", "1.Año2026", "09 SEPTIEMBRE 2026", "04-09-26")),  # Mauto
    ("{AAAA}/{Mes}/{DD}-{MM}-{AAAA}", ("Vesa", "2026", "Septiembre", "04-09-2026")),                         # la anterior
])
def test_carpeta_destino(plantilla, esperada):
    assert reglas.carpeta_destino("Vesa", date(2026, 9, 4), plantilla) == esperada


@pytest.mark.parametrize("plantilla, error", [
    (reglas.PLANTILLA_ESTANDAR, None),
    ("", "Indica la estructura"),
    ("{AAAA}/{MM}/{DIA}", "Solo se permiten las fichas"),
    ("{AAAA}/{MM}", "Debe incluir el día"),
    ("{AAAA}//{MM}-{DD}", "Cada carpeta"),
    ("{AAAA}/../{MM}-{DD}", "Cada carpeta"),
    ("{AAAA}/{MM}:{DD}", "no pueden llevar"),
])
def test_validar_plantilla(plantilla, error):
    resultado = reglas.validar_plantilla(plantilla)
    assert (resultado is None) if error is None else (error in resultado)


def test_fecha_de_archivo():
    assert reglas.fecha_de_archivo("24092026-ABC-Cuadre.pdf") == ("24/09/2026", date(2026, 9, 24))
    assert reglas.fecha_de_archivo("31022026-ABC-Cuadre.pdf") == ("31/02/2026", None)    # no existe
    assert reglas.fecha_de_archivo("Anulacion.pdf") is None
    assert reglas.fecha_de_archivo("240920261-ABC.pdf") is None                         # 9 dígitos


def test_adjuntos_auxiliares_se_guardan_si_hay_uno_con_formato():
    ok = reglas.clasificar("Corte VESA 24/09/2026", [PDF, "Anulacion.pdf", "firma.png"], EMPRESAS, HOY)
    assert ok.valida and ok.adjuntos_validos == (PDF, "Anulacion.pdf")
    solo_auxiliar = reglas.clasificar("Corte VESA 24/09/2026", ["Anulacion.pdf"], EMPRESAS, HOY)
    assert not solo_auxiliar.valida and "FECHA-EMPRESA-DOCUMENTO" in str(solo_auxiliar.errores[0])
    otra_extension = reglas.clasificar("Corte VESA 24/09/2026", [PDF, "notas.docx"], EMPRESAS, HOY)
    assert [e.titulo for e in otra_extension.errores] == ["Error en archivo adjunto"]


def test_la_fecha_de_los_archivos_debe_ser_la_del_asunto():
    c = reglas.clasificar("Corte VESA 24/09/2026", [PDF, "25092026-ABC-Depositos.pdf", "Anulacion.pdf"], EMPRESAS, HOY)
    [error] = c.errores
    assert error.titulo == "Error en fechas" and "'25092026-ABC-Depositos.pdf' (25/09/2026)" in error.detalle
    assert PDF not in error.detalle and "Anulacion" not in error.detalle     # los auxiliares no se comparan


@pytest.mark.parametrize("asunto", [
    "Corte de caja VESA",               # sin fecha
    "Corte de caja VESA 24/09/2025",    # año del año pasado fuera de la gracia (error frecuente)
    "Corte de caja VESA 24/10/2026",    # futura
])
def test_fecha_rescatada_del_nombre_del_archivo(asunto):
    c = reglas.clasificar(asunto, ["Anulacion.pdf", PDF], EMPRESAS, HOY)
    assert c.valida and c.fecha == date(2026, 9, 24)


def test_sin_fecha_valida_en_asunto_ni_archivos_se_rechaza():
    c = reglas.clasificar("Corte de caja VESA", ["29092026-ABC-Cuadre.pdf"], EMPRESAS, HOY)   # archivo con fecha futura
    assert not c.valida and "No se encontró una fecha" in str(c.errores[0])


@pytest.mark.parametrize("asunto, cuerpo, sin_movimiento", [
    ("Corte VESA 24/09/2026", "Buen día, hoy no hubo movimiento.", True),
    ("Corte VESA 24/09/2026 sin movimineto", "", True),                       # error de escritura
    ("Corte VESA 24/09/2026", "<p>No se realizaron ventas el d&iacute;a de hoy</p>", True),
    ("Corte VESA 24/09/2026", "No hubo ningún tipo de movimiento en caja", True),
    ("Corte VESA 24/09/2026", "Ventas: 0", True),
    ("Caja cerrada 24/09/2026", "", True),
    ("Corte VESA 24/09/2026", "Sin novedades que reportar", True),
    # Falsos positivos del prototipo: estos correos solo olvidaron los adjuntos y deben rechazarse.
    ("Corte VESA 24/09/2026", "Envío el corte en 05/10/2026", False),
    ("Corte VESA 24/09/2026", "Adjunto corte, no olvidar revisar las ventas del día.", False),
    ("Corte VESA 24/09/2026", "Adjunto el corte. N/A", False),
    ("Corte VESA 24/09/2026", "Adjunto el corte." + " relleno" * 80 + " no hubo movimiento", False),   # fuera del inicio
])
def test_indica_sin_movimiento(asunto, cuerpo, sin_movimiento):
    assert reglas.indica_sin_movimiento(asunto, cuerpo) is sin_movimiento


def test_sin_movimiento_solo_si_no_trae_archivos_de_corte():
    assert reglas.es_sin_movimiento("Corte VESA sin movimiento", "", ["firma.png"])
    assert not reglas.es_sin_movimiento("Corte VESA sin movimiento", "", [PDF])


# ======================================================================== archivador

def test_archivador_no_duplica_el_mismo_contenido(tmp_path):
    a = Archivador(tmp_path)
    partes = ("VESA", "2026", "Septiembre", "24-09-2026")
    primero = a.guardar(partes, PDF, b"uno")
    repetido = a.guardar(partes, PDF, b"uno")
    correccion = a.guardar(partes, PDF, b"dos")
    correccion_repetida = a.guardar(partes, PDF, b"dos")
    assert (primero.nombre, primero.duplicado) == (PDF, False)
    assert (repetido.nombre, repetido.duplicado) == (PDF, True)
    assert (correccion.nombre, correccion.duplicado) == ("24092026-ABC-Cuadre (1).pdf", False)
    assert correccion_repetida.duplicado and correccion_repetida.nombre == correccion.nombre
    carpeta = tmp_path.joinpath(*partes)
    assert sorted(p.name for p in carpeta.iterdir()) == sorted([PDF, "24092026-ABC-Cuadre (1).pdf"])


def test_archivador_no_sale_de_la_raiz(tmp_path):
    with pytest.raises(ValueError):
        Archivador(tmp_path / "raiz").guardar(("..", "fuera"), PDF, b"x")


# ======================================================================= tarea

class BuzonFalso:
    def __init__(self, correos=(), falla_mover=()):
        self.bandeja = list(correos)
        self.carpetas: dict[str, list[Correo]] = {}
        self.respuestas: list[tuple[str, str, str]] = []
        self.falla_mover = set(falla_mover)

    def pendientes(self, limite, desde=None):
        return [c for c in self.bandeja if desde is None or c.recibido >= desde][:limite]

    def responder(self, correo, asunto, html):
        self.respuestas.append((correo.remitente, asunto, html))

    def mover(self, correo, carpeta):
        if correo.message_id in self.falla_mover:
            raise ConnectionError("EWS no responde")
        self.bandeja.remove(correo)
        self.carpetas.setdefault(carpeta, []).append(correo)

    def en(self, carpeta):
        return [c.message_id for c in self.carpetas.get(carpeta, [])]


def correo(n, asunto="Corte de caja VESA 24/09/2026", remitente="caja@canella.com.gt", adjuntos=((PDF, b"%PDF"),), cuerpo="", **enc):
    return Correo(id=f"id{n}", message_id=f"<m{n}@canella>", asunto=asunto, remitente=remitente,
                  recibido=datetime(2026, 9, 24, 12, n), encabezados=enc, adjuntos=tuple(Adjunto(a, b) for a, b in adjuntos),
                  cuerpo=cuerpo)


@pytest.fixture
def entorno(app, tmp_path, monkeypatch):
    """Configuración completa, empresas sembradas y fábricas apuntando a dobles de prueba."""
    variables = {
        "CORTE_CAJA_DESTINO": str(tmp_path / "destino"),
        "CORTE_CAJA_BUZON": "automatizacionescaja@canella.com.gt", "CORTE_CAJA_EWS_SERVIDOR": "owa.prueba",
        "CORTE_CAJA_EWS_USUARIO": "robot", "CORTE_CAJA_EWS_CONTRASENA": "x", "CORTE_CAJA_DOMINIOS": "canella.com.gt",
        "CORTE_CAJA_LOTE": "20", "CORTE_CAJA_RECIBIDOS_DESDE": "",
    }
    for k, v in variables.items():
        monkeypatch.setenv(k, v)
    for orden, e in enumerate(EMPRESAS):
        db.session.add(FilaEmpresa(carpeta=e.carpeta, palabras_clave=",".join(e.palabras_clave), orden=orden))
    db.session.commit()
    buzon = BuzonFalso()
    monkeypatch.setattr(servicios, "crear_buzon", lambda config: buzon)
    return buzon, tmp_path / "destino"


def procesar():
    return ejecutar_tarea("corte_caja", "procesar", proceso="prueba", parametros={"hoy": HOY.isoformat()})


def test_correo_valido_se_archiva_y_se_mueve(entorno):
    buzon, destino = entorno
    buzon.bandeja.append(correo(1, adjuntos=((PDF, b"%PDF"), ("firma.png", b"img"))))
    r = procesar()
    assert r.estado == "exito"
    assert buzon.en("Procesados") == ["<m1@canella>"] and not buzon.respuestas
    assert destino.joinpath(*DIA_VESA, PDF).read_bytes() == b"%PDF"
    fila = FilaCorreo.query.one()
    assert (fila.estado, fila.empresa, fila.fecha_corte, fila.simulado) == ("procesado", "VESA", date(2026, 9, 24), False)
    assert [a.nombre_final for a in fila.archivos] == [PDF] and fila.ejecucion_id == r.id
    assert fila.archivos[0].carpeta == "/".join(DIA_VESA)


def test_cada_empresa_usa_su_plantilla_de_carpetas(entorno):
    buzon, destino = entorno
    FilaEmpresa.query.filter_by(carpeta="Mauto").one().plantilla_carpeta = "1.Año{AAAA}/{MM} {MES} {AAAA}/{DD}-{MM}-{AA}"
    db.session.commit()
    buzon.bandeja.append(correo(1, asunto="Corte Mauto 24/09/2026"))
    procesar()
    assert (destino / "Mauto" / "1.Año2026" / "09 SEPTIEMBRE 2026" / "24-09-26" / PDF).exists()


def test_adjuntos_auxiliares_se_archivan_junto_al_corte(entorno):
    buzon, destino = entorno
    buzon.bandeja.append(correo(1, adjuntos=((PDF, b"%PDF"), ("Anulacion.pdf", b"%PDF-anula"))))
    procesar()
    assert sorted(p.name for p in destino.joinpath(*DIA_VESA).iterdir()) == ["24092026-ABC-Cuadre.pdf", "Anulacion.pdf"]


def test_sin_movimiento_se_registra_sin_responder(entorno):
    buzon, destino = entorno
    buzon.bandeja.append(correo(1, adjuntos=(("firma.png", b"img"),), cuerpo="Buenas tardes, hoy no hubo movimiento."))
    r = procesar()
    assert r.estado == "exito" and json.loads(r.resultado)["sin_movimiento"] == 1
    assert buzon.en("Sin movimiento") == ["<m1@canella>"] and not buzon.respuestas and not destino.exists()
    fila = FilaCorreo.query.one()
    assert (fila.estado, fila.empresa, fila.fecha_corte) == ("sin_movimiento", "VESA", date(2026, 9, 24))


def test_correo_sin_adjuntos_que_no_avisa_sin_movimiento_se_rechaza(entorno):
    buzon, _ = entorno
    buzon.bandeja.append(correo(1, adjuntos=(), cuerpo="Envío el corte en 24/09/2026, no olvidar revisar las ventas."))
    procesar()
    assert buzon.en("Rechazados") == ["<m1@canella>"]
    assert "no contiene archivos adjuntos" in buzon.respuestas[0][2]


def test_correo_invalido_se_rechaza_solo_al_remitente_y_escapado(entorno):
    buzon, destino = entorno
    buzon.bandeja.append(correo(1, asunto='Corte <a href="http://malo">clic</a> 24/09/2026'))
    procesar()
    assert buzon.en("Rechazados") == ["<m1@canella>"]
    [(para, asunto, html)] = buzon.respuestas
    assert para == "caja@canella.com.gt" and asunto == servicios.ASUNTO_RECHAZO
    assert '<a href="http://malo">' not in html and "&lt;a href=" in html
    assert "No se reconoció la empresa" in html
    assert not destino.exists()
    assert FilaCorreo.query.one().estado == "rechazado"


def test_externos_y_automaticos_se_ignoran_sin_responder(entorno):
    buzon, _ = entorno
    buzon.bandeja += [correo(1, remitente="alguien@gmail.com"), correo(2, **{"auto-submitted": "auto-replied"})]
    procesar()
    assert buzon.en("Ignorados") == ["<m1@canella>", "<m2@canella>"] and not buzon.respuestas
    assert {f.estado for f in FilaCorreo.query} == {"ignorado"}


def test_un_correo_con_error_no_detiene_a_los_demas(entorno):
    buzon, _ = entorno
    buzon.bandeja += [correo(1, adjuntos=((PDF, b""),)), correo(2)]  # adjunto vacío → error
    r = procesar()
    assert r.estado == "advertencia"
    assert buzon.en("Error") == ["<m1@canella>"] and buzon.en("Procesados") == ["<m2@canella>"]
    assert sorted(f.estado for f in FilaCorreo.query) == ["error", "procesado"]


def test_si_no_se_puede_mover_se_reintenta_sin_duplicar_archivos(entorno):
    buzon, destino = entorno
    buzon.falla_mover = {"<m1@canella>"}
    buzon.bandeja.append(correo(1))
    assert procesar().estado == "advertencia"
    assert buzon.bandeja and buzon.bandeja[0].message_id == "<m1@canella>"   # sigue pendiente

    buzon.falla_mover = set()
    procesar()
    archivos = list(destino.joinpath(*DIA_VESA).iterdir())
    assert [p.name for p in archivos] == [PDF]
    ultima = FilaCorreo.query.filter_by(estado="procesado").one()
    assert ultima.archivos[0].duplicado is True


def test_sin_correos_termina_sin_cambios(entorno):
    r = procesar()
    assert r.estado == "sin_cambios" and FilaCorreo.query.count() == 0


def test_modo_simulacion_ya_no_existe(entorno, monkeypatch):
    # Retirado el 27/11/2026: aunque el .env aún diga «simulacion», la tarea responde, guarda y mueve.
    buzon, destino = entorno
    monkeypatch.setenv("CORTE_CAJA_MODO", "simulacion")
    buzon.bandeja += [correo(1), correo(2, asunto="hola")]
    procesar()
    assert not buzon.bandeja and buzon.respuestas and destino.joinpath(*DIA_VESA, PDF).exists()
    assert {f.simulado for f in FilaCorreo.query} == {False}


def test_recibidos_desde_excluye_correos_anteriores(entorno, monkeypatch):
    buzon, _ = entorno
    monkeypatch.setenv("CORTE_CAJA_RECIBIDOS_DESDE", "2026-09-24T12:02")
    buzon.bandeja += [correo(1), correo(3)]
    procesar()
    assert buzon.en("Procesados") == ["<m3@canella>"]


def test_configuracion_incompleta_falla_con_mensaje_claro(entorno, monkeypatch):
    monkeypatch.delenv("CORTE_CAJA_DESTINO")
    r = procesar()
    assert r.estado == "error" and "CORTE_CAJA_DESTINO" in r.error


def test_fallo_de_la_corrida_revierte_filas(entorno, monkeypatch):
    buzon, _ = entorno
    buzon.bandeja.append(correo(1))
    monkeypatch.setattr(servicios._Procesador, "ejecutar", lambda self: (_ for _ in ()).throw(RuntimeError("caída")))
    assert procesar().estado == "error"
    assert FilaCorreo.query.count() == 0


# ======================================================================= tablero y CLI

def _fila(n, estado="procesado", asunto="Corte VESA 24/09/2026", remitente="caja.sala@canella.test", fecha_corte=date(2026, 9, 24),
          simulado=False, adjuntos=None, recibido=None):
    fila = FilaCorreo(ejecucion_id="x", message_id=f"<t{n}>", asunto=asunto, remitente=remitente, estado=estado,
                      recibido=recibido or datetime(2026, 9, 24, 15, n), fecha_corte=fecha_corte, simulado=simulado, adjuntos=adjuntos)
    db.session.add(fila)
    return fila


def _cajas_ejemplo():
    db.session.add_all([
        FilaCaja(categoria="CAJAS CENTRALES", nombre_caja="SALA DE VENTAS", responsable="Persona A", correo="caja.sala@canella.test"),
        FilaCaja(categoria="CAJAS CENTRALES", nombre_caja="TALLER YAMAHA", responsable="Persona B", correo="caja.yamaha@canella.test"),
        FilaCaja(categoria="GENERAL", nombre_caja="CREDITOS COBRADORES", responsable="Cobradores", correo="se turnan los cobradores"),
    ])


def test_tablero_con_y_sin_permiso(entorno, entrar_como):
    buzon, _ = entorno
    buzon.bandeja.append(correo(1))
    procesar()
    fila = FilaCorreo.query.one()
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    inicio = c.get("/m/corte_caja/").data.decode()
    assert "Corte de caja VESA" in inicio and PDF in inicio
    for texto in ("Procesadas", "Rechazadas", "Cuadre mensual", "Aceptadas", "Tiendas registradas"):
        assert texto in inicio, texto
    assert c.get(f"/m/corte_caja/correos/{fila.id}").status_code == 200
    c.post("/salir")
    assert entrar_como(crear_usuario("otro")).get("/m/corte_caja/").status_code == 403


def test_sin_boton_revisar_buzon_ni_pantalla_de_empresas_ni_simulacion(entorno, entrar_como):
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    inicio = c.get("/m/corte_caja/").data.decode()
    assert "Revisar buzón" not in inicio and "Modo simulación" not in inicio and "Directorio de tiendas" in inicio
    assert c.post("/m/corte_caja/procesar").status_code in (404, 405)
    assert c.get("/m/corte_caja/empresas").status_code == 404


def test_kpis_y_pestanas_sin_filas_de_la_simulacion(entorno, entrar_como):
    _fila(1, adjuntos=PDF)
    _fila(2, estado="error")
    _fila(3, estado="rechazado", asunto="Corte SALA DE VENTAS sin fecha", remitente="x@canella.com.gt", adjuntos="mal.docx\nfirma.png")
    _fila(4, estado="procesado", asunto="Corte simulado", simulado=True)
    _cajas_ejemplo()
    db.session.commit()
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    procesadas = c.get("/m/corte_caja/").data.decode()
    assert procesadas.count(">Detalle</a>") == 2 and "Corte simulado" not in procesadas      # éxito y error
    assert ">Error</span>" in procesadas
    rechazadas = c.get("/m/corte_caja/?pestana=rechazadas").data.decode()
    assert "<td class=\"small\">SALA DE VENTAS</td>" in rechazadas and "mal.docx" in rechazadas   # caja y adjuntos
    assert c.get("/m/corte_caja/?pestana=rechazadas&texto=zzz").data.decode().count(">Detalle</a>") == 0


def test_cuadre_mensual_por_caja(entorno, entrar_como):
    _cajas_ejemplo()
    _fila(1)                                                                                  # SALA DE VENTAS por correo
    _fila(2, estado="sin_movimiento", remitente="otro@canella.com.gt", asunto="Taller Yamaha sin movimiento")
    _fila(3, remitente="alguien.se@canella.com.gt", asunto="Corte VESA 24/09/2026")       # no es de cobradores («se»)
    db.session.commit()
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    html = c.get("/m/corte_caja/?pestana=cuadre&mes=2026-09&dia=2026-09-24").data.decode()
    assert "Estado de cortes del 24/09/2026" in html and "Septiembre 2026" in html
    filas = {n: html.split(n, 1)[1].split("</tr>", 1)[0] for n in ("SALA DE VENTAS", "TALLER YAMAHA", "CREDITOS COBRADORES")}
    assert "Corte recibido" in filas["SALA DE VENTAS"]
    assert "Sin movimiento" in filas["TALLER YAMAHA"]
    assert "Corte no recibido" in filas["CREDITOS COBRADORES"]
    vacio = c.get("/m/corte_caja/?pestana=cuadre&mes=2026-09&dia=2026-09-23").data.decode()
    assert "Corte recibido</span>" not in vacio


def test_reglas_del_cuadre():
    cajas = [cuadre.CajaDirectorio("SALA DE VENTAS", "caja.sala@canella.test, otro@canella.com.gt"),
             cuadre.CajaDirectorio("REPUESTOS # 3", "caja.repuestos3@canella.test"),
             cuadre.CajaDirectorio("CREDITOS COBRADORES", "se turnan los cobradores")]
    assert cuadre.correos("a@x.gt; b@x.gt / texto suelto") == {"a@x.gt", "b@x.gt"}
    assert cuadre.caja_de("OTRO@canella.com.gt", "", cajas) == "SALA DE VENTAS"                # cualquiera de sus correos
    assert cuadre.caja_de("x@canella.com.gt", "corte sala de ventas", cajas) == "SALA DE VENTAS"
    assert cuadre.caja_de("x@canella.com.gt", "corte de los cobradores", cajas) == "CREDITOS COBRADORES"  # palabra distintiva
    assert cuadre.caja_de("sesion@canella.com.gt", "corte", cajas) is None                     # «se» no es un correo
    hoy = date(2026, 9, 28)
    r = cuadre.Registro(date(2026, 9, 24), cuadre.RECIBIDO, "x@canella.com.gt", "corte", destino="Canella/repuestos")
    sm = cuadre.Registro(date(2026, 9, 24), cuadre.SIN_MOVIMIENTO, "caja.repuestos3@canella.test", "sin movimiento")
    assert cuadre.estado_del_dia(date(2026, 9, 29), [], hoy) == cuadre.FUTURO
    assert cuadre.estado_del_dia(date(2026, 9, 24), [], hoy) == cuadre.NO_RECIBIDO
    assert cuadre.estado_del_dia(date(2026, 9, 24), [sm], hoy) == cuadre.SIN_MOVIMIENTO
    assert cuadre.estado_del_dia(date(2026, 9, 24), [sm, r], hoy) == cuadre.RECIBIDO
    assert cuadre.estado_de_la_caja(cajas[1], [sm]) == cuadre.SIN_MOVIMIENTO
    assert cuadre.estado_de_la_caja(cajas[1], [r]) == cuadre.NO_RECIBIDO                       # «repuestos» es genérica
    assert cuadre.dia_inicial(2026, 9, hoy) == hoy
    assert cuadre.dia_inicial(2026, 8, hoy) == date(2026, 8, 31)
    assert cuadre.dia_inicial(2026, 10, hoy) == date(2026, 10, 1)
    assert cuadre.semanas(2026, 9)[0][:2] == [None, date(2026, 9, 1)]                          # 1/9/2026 es martes


def test_directorio_de_tiendas(entorno, entrar_como):
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    assert "No hay tiendas registradas" in c.get("/m/corte_caja/cajas").data.decode()
    r = c.post("/m/corte_caja/cajas/nueva", data={"categoria": " yamaha  centrales ", "nombre_caja": "TALLER  YAMAHA",
                                                   "responsable": "Persona B", "correo": "caja.yamaha@canella.test"})
    assert r.status_code == 302
    caja = FilaCaja.query.one()
    assert (caja.categoria, caja.nombre_caja) == ("YAMAHA CENTRALES", "TALLER YAMAHA")
    c.post(f"/m/corte_caja/cajas/{caja.id}", data={"categoria": "YAMAHA CENTRALES", "nombre_caja": "TALLER YAMAHA",
                                                   "responsable": " ", "correo": ""})
    db.session.refresh(caja)
    assert caja.correo is None and caja.responsable is None
    assert "TALLER YAMAHA" in c.get("/m/corte_caja/cajas?texto=yamaha").data.decode()
    assert "No hay tiendas con esa búsqueda" in c.get("/m/corte_caja/cajas?texto=zzz").data.decode()
    malo = c.post("/m/corte_caja/cajas/nueva", data={"categoria": "X", "nombre_caja": "Y", "correo": "sin arroba"})
    assert malo.status_code == 200 and "al menos una dirección de correo" in malo.data.decode()
    c.post(f"/m/corte_caja/cajas/{caja.id}/eliminar")
    assert FilaCaja.query.count() == 0


def test_directorio_pagina_de_15_en_15_y_conserva_la_busqueda(entorno, entrar_como):
    for n in range(20):
        db.session.add(FilaCaja(categoria="YAMAHA DEPARTAMENTOS", nombre_caja=f"CAJA {n:02d}", correo=f"caja{n}@canella.com.gt"))
    db.session.add(FilaCaja(categoria="GENERAL", nombre_caja="CORPORATIVO", correo="corp@canella.com.gt"))
    db.session.commit()
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    p1 = c.get("/m/corte_caja/cajas").get_data(as_text=True)
    assert p1.count(">Editar</a>") == 15 and "de <span>21</span> tiendas" in p1
    assert c.get("/m/corte_caja/cajas?pagina=2").get_data(as_text=True).count(">Editar</a>") == 6
    buscado = c.get("/m/corte_caja/cajas?texto=yamaha").get_data(as_text=True)
    assert "de <span>20</span> tiendas" in buscado and "texto=yamaha" in buscado and "pagina=2" in buscado   # el enlace conserva el filtro
    assert c.get("/m/corte_caja/cajas?texto=yamaha&pagina=2").get_data(as_text=True).count(">Editar</a>") == 5


# Registros con la forma real de los JSON del prototipo (transfer_logs.json y rejected_logs.json).
TRANSFER = [
    # Formato viejo: un registro por archivo; los tres primeros son el mismo correo.
    {"timestamp": "2026-10-09 08:15:01", "filename": "09102026-CAN-CORTE SAP.pdf", "status": "EXITO", "message": "[NORMAL] Guardado",
     "destino": "\\\\128.1.200.171\\Cortes-de-caja$\\Cortes_de_caja_prueba\\CANELLA\\2026\\Octubre\\09-10-2026",
     "asunto": "Corte de Caja, Canella, 09/10/2026\t", "remitente": "caja.sala@canella.test"},
    {"timestamp": "2026-10-09 08:15:03", "filename": "09102026-CAN-DEPOSITOS.pdf", "status": "EXITO", "message": "[NORMAL] Guardado",
     "destino": "\\\\128.1.200.171\\Cortes-de-caja$\\Cortes_de_caja_prueba\\CANELLA\\2026\\Octubre\\09-10-2026",
     "asunto": "Corte de Caja, Canella, 09/10/2026\t", "remitente": "caja.sala@canella.test"},
    {"timestamp": "2026-10-09 08:15:04", "filename": "Anulacion.pdf", "status": "EXITO", "message": "[NORMAL] Guardado",
     "destino": "\\\\128.1.200.171\\Cortes-de-caja$\\Cortes_de_caja_prueba\\CANELLA\\2026\\Octubre\\09-10-2026",
     "asunto": "Corte de Caja, Canella, 09/10/2026\t", "remitente": "caja.sala@canella.test"},
    # Mismo asunto pero una hora después: es otro correo (un reenvío).
    {"timestamp": "2026-10-09 09:20:00", "filename": "09102026-CAN-CORTE SAP.pdf", "status": "EXITO", "message": "[NORMAL] Guardado",
     "destino": "\\\\128.1.200.171\\Cortes-de-caja$\\Cortes_de_caja_prueba\\CANELLA\\2026\\Octubre\\09-10-2026",
     "asunto": "Corte de Caja, Canella, 09/10/2026\t", "remitente": "caja.sala@canella.test"},
    # Formato nuevo: la lista de archivos del correo; carpeta con la estructura oficial y sin fecha en el asunto.
    {"timestamp": "2026-11-05 17:40:10", "filename": ["05112026-MRC-CORTE.pdf", "05112026-MRC-DEPOSITOS.pdf"], "status": "EXITO",
     "message": "Se guardaron 2 archivos correctamente.",
     "destino": "\\\\128.1.200.171\\Cortes-de-caja$\\MR. Credit\\1.Año 2026\\202611NOVIEMBRE\\05-11-26",
     "asunto": "Corte de caja Mr Credit", "remitente": "cobros.credito@canella.test", "fecha_corte": ""},
    {"timestamp": "2026-11-05 18:02:00", "filename": ["(Sin movimiento)"], "status": "SIN MOVIMIENTO", "message": "Sin movimiento",
     "destino": "Sin carpeta (Validación omitida)", "asunto": "Corte VESA 05/11/2026 sin movimiento", "remitente": "caja.vesa@canella.test",
     "fecha_corte": "05-11-2026"},
    {"timestamp": "2026-11-05 18:05:00", "filename": "boletin.pdf", "status": "IGNORADO", "message": "Remitente externo",
     "destino": "", "asunto": "Boletín", "remitente": "Desconocido"},
    {"timestamp": "2026-11-05 18:06:00", "filename": "x.pdf", "status": "RARO", "message": "", "destino": "", "asunto": "", "remitente": ""},
]
RECHAZADOS = [
    {"timestamp": "2026-10-08 12:23:55", "caja": "SALA DE VENTAS", "asunto": "Corte de Caja, Vesa, 0510/2026",
     "motivo": "<b>Error en el Asunto:</b> No se encontró una fecha válida / <b>Error en Archivos:</b> El correo <strong>no contiene</strong>",
     "archivos": ["05102026-CAJAVESA-DEPOSITOS.pdf"], "remitente": "caja.sala@canella.test"},
]


def test_historial_del_prototipo_se_reagrupa_por_correo():
    empresas = [reglas.Empresa("Canella", ("canella",)), reglas.Empresa("Vesa", ("vesa", "besa")),
                reglas.Empresa("Mister Credit", ("mr credit", "mister credit"))]
    correos, omitidos = historial.convertir_procesados(TRANSFER, empresas)
    assert omitidos == ["RARO"]
    primero, reenvio, mrc, sin_mov, ignorado = correos
    assert primero.adjuntos == ("09102026-CAN-CORTE SAP.pdf", "09102026-CAN-DEPOSITOS.pdf", "Anulacion.pdf")
    assert (primero.estado, primero.empresa, primero.fecha_corte) == ("procesado", "Canella", date(2026, 10, 9))
    assert primero.recibido == datetime(2026, 10, 9, 14, 15, 1)              # 08:15 en Guatemala = 14:15 UTC
    assert reenvio.adjuntos == ("09102026-CAN-CORTE SAP.pdf",) and reenvio.message_id != primero.message_id
    assert (mrc.empresa, mrc.fecha_corte, len(mrc.adjuntos)) == ("Mister Credit", date(2026, 11, 5), 2)   # fecha de la carpeta
    assert (sin_mov.estado, sin_mov.adjuntos, sin_mov.fecha_corte, sin_mov.empresa) == ("sin_movimiento", (), date(2026, 11, 5), "Vesa")
    assert (ignorado.estado, ignorado.remitente, ignorado.motivo) == ("ignorado", "", "Remitente externo")
    [rechazado] = historial.convertir_rechazados(RECHAZADOS, empresas)
    assert rechazado.motivo == "Error en el Asunto: No se encontró una fecha válida\nError en Archivos: El correo no contiene"
    assert (rechazado.estado, rechazado.empresa, rechazado.adjuntos) == ("rechazado", "Vesa", ("05102026-CAJAVESA-DEPOSITOS.pdf",))
    # Mismo segundo, remitente y asunto: otros archivos o copia exacta → cada uno su identificador, estable.
    mismo_segundo = [RECHAZADOS[0], {**RECHAZADOS[0], "archivos": ["image002.png"]}, RECHAZADOS[0]]
    ids = [c.message_id for c in historial.convertir_rechazados(mismo_segundo, empresas)]
    assert len(set(ids)) == 3 and ids[0] == rechazado.message_id
    assert ids == [c.message_id for c in historial.convertir_rechazados(mismo_segundo, empresas)]


def test_cli_importa_el_historial_sin_duplicar(entorno, app, entrar_como, tmp_path):
    procesados, rechazados = tmp_path / "transfer_logs.json", tmp_path / "rejected_logs.json"
    procesados.write_text(json.dumps(TRANSFER), encoding="utf-8")
    rechazados.write_text(json.dumps(RECHAZADOS), encoding="utf-8")
    runner = app.test_cli_runner()
    argumentos = ["corte_caja", "historial-importar", "--procesados", str(procesados), "--rechazados", str(rechazados)]
    primera = runner.invoke(args=argumentos)
    assert primera.exit_code == 0 and "6 correos en los archivos, 6 agregados" in primera.output, primera.output
    assert "CORTE_CAJA_RECIBIDOS_DESDE=2026-11-06T00:06" in primera.output and "RARO" in primera.output
    assert "0 agregados" in runner.invoke(args=argumentos).output                                  # se puede repetir
    assert FilaCorreo.query.filter_by(ejecucion_id=historial.EJECUCION_IMPORTADA).count() == 6
    assert runner.invoke(args=["corte_caja", "historial-importar"]).exit_code != 0                 # sin archivos

    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    tablero = c.get("/m/corte_caja/").data.decode()
    assert "Anulacion.pdf" in tablero or "3 archivos" in tablero
    assert "05102026-CAJAVESA-DEPOSITOS.pdf" in c.get("/m/corte_caja/?pestana=rechazadas").data.decode()


def test_cli_importa_el_directorio_del_prototipo(entorno, app, tmp_path):
    import sqlite3
    ruta = tmp_path / "cajas.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE cajas_directorio (id INTEGER PRIMARY KEY, categoria TEXT, nombre_caja TEXT, responsable TEXT, correo TEXT)")
    con.executemany("INSERT INTO cajas_directorio (categoria, nombre_caja, responsable, correo) VALUES (?, ?, ?, ?)", [
        ("CAJAS CENTRALES", "SALA DE VENTAS", "Persona A", "caja.sala@canella.test"),
        ("GENERAL", "CREDITOS COBRADORES", "Cobradores", "se turnan los cobradores"),
        ("", "SIN CATEGORIA", None, None),
    ])
    con.commit()
    con.close()
    runner = app.test_cli_runner()
    primera = runner.invoke(args=["corte_caja", "cajas-importar", str(ruta)])
    assert primera.exit_code == 0 and "3 cajas leídas, 2 agregadas" in primera.output, primera.output
    assert "0 agregadas" in runner.invoke(args=["corte_caja", "cajas-importar", str(ruta)]).output   # se puede repetir
    assert FilaCaja.query.count() == 2


def test_cli_empresas(entorno, app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["corte_caja", "empresa-agregar", "NUEVA", "--claves", "nueva,nva", "--orden", "3"]).exit_code == 0
    assert runner.invoke(args=["corte_caja", "empresa-modificar", "NUEVA", "--inactiva"]).exit_code == 0
    salida = runner.invoke(args=["corte_caja", "empresas"]).output
    assert "NUEVA" in salida and "inactiva" in salida and reglas.PLANTILLA_ESTANDAR in salida
    assert runner.invoke(args=["corte_caja", "empresa-modificar", "NO_EXISTE", "--orden", "1"]).exit_code != 0
    canella = "1.Año{AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}"
    assert runner.invoke(args=["corte_caja", "empresa-modificar", "NUEVA", "--plantilla", canella]).exit_code == 0
    assert FilaEmpresa.query.filter_by(carpeta="NUEVA").one().plantilla_carpeta == canella
    mala = runner.invoke(args=["corte_caja", "empresa-modificar", "NUEVA", "--plantilla", "{AAAA}/{MM}"])
    assert mala.exit_code != 0 and "Plantilla inválida" in mala.output



def test_panel_pagina_de_15_en_15(entorno, entrar_como):
    from app.core.paginacion import POR_PAGINA
    assert POR_PAGINA == 15
    for n in range(20):
        db.session.add(FilaCorreo(ejecucion_id="x", message_id=f"<p{n}>", asunto=f"Corte VESA {n}", remitente="a@canella.com.gt",
                                  recibido=datetime(2026, 9, 20, 8, n), estado="procesado"))
    db.session.commit()
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    p1 = c.get("/m/corte_caja/").get_data(as_text=True)
    assert p1.count(">Detalle</a>") == 15 and "de <span>20</span>" in p1
    assert c.get("/m/corte_caja/?pagina=2").get_data(as_text=True).count(">Detalle</a>") == 5
