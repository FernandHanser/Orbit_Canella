"""Módulo corte_caja: reglas, archivador, tarea con buzón simulado y panel.

Sin buzón ni carpeta de red reales: ``BuzonFalso`` reemplaza a EWS y el destino es ``tmp_path``.
"""
from datetime import date, datetime

import pytest

from app.core.ejecuciones import ejecutar_tarea
from app.core.models import Ejecucion
from app.extensions import db
from app.modulos.corte_caja import reglas, servicios
from app.modulos.corte_caja.archivador import Archivador
from app.modulos.corte_caja.buzon import Adjunto, Correo
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


def test_carpeta_destino():
    assert reglas.carpeta_destino("VESA", date(2026, 9, 4)) == ("VESA", "2026", "Septiembre", "04-09-2026")


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


def correo(n, asunto="Corte de caja VESA 24/09/2026", remitente="caja@canella.com.gt", adjuntos=((PDF, b"%PDF"),), **enc):
    return Correo(id=f"id{n}", message_id=f"<m{n}@canella>", asunto=asunto, remitente=remitente,
                  recibido=datetime(2026, 9, 24, 12, n), encabezados=enc, adjuntos=tuple(Adjunto(a, b) for a, b in adjuntos))


@pytest.fixture
def entorno(app, tmp_path, monkeypatch):
    """Configuración completa, empresas sembradas y fábricas apuntando a dobles de prueba."""
    variables = {
        "CORTE_CAJA_MODO": "real", "CORTE_CAJA_DESTINO": str(tmp_path / "destino"),
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
    assert (destino / "VESA" / "2026" / "Septiembre" / "24-09-2026" / PDF).read_bytes() == b"%PDF"
    fila = FilaCorreo.query.one()
    assert (fila.estado, fila.empresa, fila.fecha_corte, fila.simulado) == ("procesado", "VESA", date(2026, 9, 24), False)
    assert [a.nombre_final for a in fila.archivos] == [PDF] and fila.ejecucion_id == r.id


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
    archivos = list((destino / "VESA" / "2026" / "Septiembre" / "24-09-2026").iterdir())
    assert [p.name for p in archivos] == [PDF]
    ultima = FilaCorreo.query.filter_by(estado="procesado").one()
    assert ultima.archivos[0].duplicado is True


def test_sin_correos_termina_sin_cambios(entorno):
    r = procesar()
    assert r.estado == "sin_cambios" and FilaCorreo.query.count() == 0


def test_simulacion_no_toca_nada_y_no_repite(entorno, monkeypatch):
    buzon, destino = entorno
    monkeypatch.setenv("CORTE_CAJA_MODO", "simulacion")
    buzon.bandeja += [correo(1), correo(2, asunto="hola")]
    procesar()
    assert len(buzon.bandeja) == 2 and not buzon.carpetas and not buzon.respuestas and not destino.exists()
    assert sorted((f.estado, f.simulado) for f in FilaCorreo.query) == [("procesado", True), ("rechazado", True)]
    assert procesar().estado == "sin_cambios"                     # la siguiente corrida no los repite
    assert FilaCorreo.query.count() == 2


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


# ======================================================================= panel y CLI

def test_panel_con_y_sin_permiso(entorno, entrar_como):
    buzon, _ = entorno
    buzon.bandeja.append(correo(1))
    procesar()
    fila = FilaCorreo.query.one()
    con = crear_usuario("cajas", modulos=["corte_caja"])
    c = entrar_como(con)
    inicio = c.get("/m/corte_caja/")
    assert inicio.status_code == 200 and b"Corte de caja VESA" in inicio.data
    assert c.get(f"/m/corte_caja/correos/{fila.id}").status_code == 200
    assert b"MR. Credit" in c.get("/m/corte_caja/empresas").data
    c.post("/salir")

    sin = crear_usuario("otro")
    assert entrar_como(sin).get("/m/corte_caja/").status_code == 403


def test_boton_revisar_buzon(entorno, entrar_como):
    buzon, _ = entorno
    buzon.bandeja.append(correo(1))
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    r = c.post("/m/corte_caja/procesar", follow_redirects=True)
    assert r.status_code == 200 and "Revisión del buzón terminada".encode() in r.data
    assert Ejecucion.query.filter_by(modulo_id="corte_caja").one().usuario_id is not None


def test_cli_empresas(entorno, app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["corte_caja", "empresa-agregar", "NUEVA", "--claves", "nueva,nva", "--orden", "3"]).exit_code == 0
    assert runner.invoke(args=["corte_caja", "empresa-modificar", "NUEVA", "--inactiva"]).exit_code == 0
    salida = runner.invoke(args=["corte_caja", "empresas"]).output
    assert "NUEVA" in salida and "inactiva" in salida
    assert runner.invoke(args=["corte_caja", "empresa-modificar", "NO_EXISTE", "--orden", "1"]).exit_code != 0


def test_boton_revisar_con_spinner_y_confirmacion_solo_en_modo_real(entorno, entrar_como, monkeypatch):
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    real = c.get("/m/corte_caja/").data.decode()
    assert 'data-cargando="Revisando buzón…"' in real and "data-confirmar=" in real
    assert "js/interaccion.js" in real and 'id="modal-confirmar"' in real

    monkeypatch.setenv("CORTE_CAJA_MODO", "simulacion")
    simulacion = c.get("/m/corte_caja/").data.decode()
    assert 'data-cargando="Revisando buzón…"' in simulacion and "data-confirmar=" not in simulacion


# ======================================================================= CRUD de empresas

def test_empresas_solo_lectura_para_usuarios_del_modulo(entorno, entrar_como):
    c = entrar_como(crear_usuario("cajas", modulos=["corte_caja"]))
    lista = c.get("/m/corte_caja/empresas").data.decode()
    assert "MR. Credit" in lista and "Nueva empresa" not in lista and "Editar" not in lista
    vesa = FilaEmpresa.query.filter_by(carpeta="VESA").one()
    assert c.get("/m/corte_caja/empresas/nueva").status_code == 403
    assert c.post("/m/corte_caja/empresas/nueva", data={"carpeta": "X", "palabras_clave": "x", "orden": 1}).status_code == 403
    assert c.post(f"/m/corte_caja/empresas/{vesa.id}", data={"carpeta": "Y", "palabras_clave": "y", "orden": 1}).status_code == 403
    assert c.post(f"/m/corte_caja/empresas/{vesa.id}/eliminar").status_code == 403
    assert FilaEmpresa.query.filter_by(carpeta="VESA").one().palabras_clave == "vesa,besa"


def test_admin_crea_edita_y_elimina_empresas(entorno, entrar_como):
    from app.core.models import Usuario
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["corte_caja"]))
    assert "Nueva empresa" in c.get("/m/corte_caja/empresas").data.decode()

    r = c.post("/m/corte_caja/empresas/nueva", data={"carpeta": "AUTOS GT", "palabras_clave": " Autos GT, autos gt ,ÁUTOSGT,, ", "orden": "70", "activa": "y"})
    assert r.status_code == 302
    nueva = FilaEmpresa.query.filter_by(carpeta="AUTOS GT").one()
    assert nueva.palabras_clave == "autos gt,áutosgt" and nueva.orden == 70 and nueva.activa   # sin repetidas

    c.post(f"/m/corte_caja/empresas/{nueva.id}", data={"carpeta": "AUTOS GT", "palabras_clave": "autosgt", "orden": "75"})
    db.session.refresh(nueva)
    assert (nueva.palabras_clave, nueva.orden, nueva.activa) == ("autosgt", 75, False)       # interruptor apagado

    c.post(f"/m/corte_caja/empresas/{nueva.id}/eliminar")
    assert FilaEmpresa.query.filter_by(carpeta="AUTOS GT").first() is None


def test_validaciones_de_empresa(entorno, entrar_como):
    from app.core.models import Usuario
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["corte_caja"]))
    for datos, mensaje in [
        ({"carpeta": "vesa", "palabras_clave": "x", "orden": "1"}, "Ya existe una empresa con esa carpeta"),
        ({"carpeta": "A/B", "palabras_clave": "x", "orden": "1"}, "Sin los caracteres"),
        ({"carpeta": "Nueva.", "palabras_clave": "x", "orden": "1"}, "ni terminar en punto"),
        ({"carpeta": "Nueva", "palabras_clave": " , ,", "orden": "1"}, "al menos una palabra clave"),
    ]:
        r = c.post("/m/corte_caja/empresas/nueva", data=datos)
        assert r.status_code == 200 and mensaje in r.data.decode(), mensaje
    assert FilaEmpresa.query.count() == len(EMPRESAS)


def test_no_se_elimina_una_empresa_con_historial(entorno, entrar_como):
    from app.core.models import Usuario
    buzon, _ = entorno
    buzon.bandeja.append(correo(1))            # VESA
    procesar()
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["corte_caja"]))
    vesa = FilaEmpresa.query.filter_by(carpeta="VESA").one()
    r = c.post(f"/m/corte_caja/empresas/{vesa.id}/eliminar", follow_redirects=True)
    assert "desactívala en lugar de eliminarla" in r.data.decode()
    assert FilaEmpresa.query.filter_by(carpeta="VESA").one()


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
