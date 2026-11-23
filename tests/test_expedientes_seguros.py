"""Módulo expedientes_seguros: reglas, PDF, visor, generación del paquete, correo y configuración.

SAP se simula (``SapFalso``) y el expediente es un PDF generado en la prueba: nada real ni con
datos personales.
"""
import email
import io
import os
from datetime import date, timedelta
from email import policy

import pytest
from pypdf import PdfReader, PdfWriter

from app.extensions import db
from app.modulos.expedientes_seguros import reglas, servicios
from app.modulos.expedientes_seguros.models import Aseguradora, CodigoAseguradora, Documento, Paquete, Parametro
from app.modulos.expedientes_seguros import configuracion
from app.modulos.expedientes_seguros.sap import Anexo, Factura, Llamada, Pendiente, SapNoDisponible

from .conftest import contar_consultas, crear_usuario


def pdf(paginas, ancho=612):
    """PDF con ``paginas`` hojas de anchos distintos para reconocerlas después."""
    w = PdfWriter()
    for i in range(paginas):
        w.add_blank_page(ancho + i, 792)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def anchos(datos):
    return [int(p.mediabox.width) for p in PdfReader(io.BytesIO(datos)).pages]


# =========================================================================== reglas

def test_nombre_del_paquete_sin_caracteres_invalidos():
    assert reglas.nombre_paquete(51595, "ASEGURADORA LA CEIBA, S. A.", date(2026, 9, 28)) == "51595_ASEGURADORA LA CEIBA, S. A_2026-09-28.pdf"
    assert reglas.nombre_paquete(1, 'G&T / "X"', date(2026, 1, 2)) == "1_G&T X_2026-01-02.pdf"
    assert reglas.nombre_factura(51595, "MAPFRE") == "FAC 51595-MAPFRE.pdf"


def test_rangos_y_paginas_elegidas():
    assert reglas.rangos([7, 1, 2, 3, 9, 10]) == "1-3, 7, 9-10"
    assert reglas.paginas_elegidas(["3", "1", "3", "0", "99", "x"], 10) == [1, 3]


def test_es_dpi_por_el_nombre_del_anexo():
    assert reglas.es_dpi("DPI P-828JGG, LLAMADA 82360, RECLAMO 642772") is True
    assert reglas.es_dpi("  dpi algo") is True
    assert reglas.es_dpi("82360") is False
    assert reglas.es_dpi("") is False


def test_mapa_de_paginas_combina_varios_anexos_en_un_solo_consecutivo():
    mapa = reglas.mapa_paginas([(1, 3), (2, 1)])
    assert mapa == {1: (1, 1), 2: (1, 2), 3: (1, 3), 4: (2, 1)}
    assert reglas.paginas_por_linea([3, 4], mapa) == {1: [3], 2: [1]}


def test_plantilla_solo_reemplaza_variables_conocidas():
    datos = {"aseguradora": "MAPFRE", "serie": "87BC", "numero": "358"}
    assert reglas.aplicar_plantilla("{aseguradora}//Serie: {serie} Número: {numero}//CANELLA", datos) == "MAPFRE//Serie: 87BC Número: 358//CANELLA"
    assert reglas.aplicar_plantilla("{aseguradora.__class__} {otra}", datos) == "{aseguradora.__class__} {otra}"


def test_direcciones_y_validacion():
    assert reglas.direcciones("a@canella.com.gt; Gustavo <gestrada@canella.com.gt>, ") == ["a@canella.com.gt", "gestrada@canella.com.gt"]
    assert reglas.correo_invalido("a@canella.com.gt; malo@") == "malo@"
    assert reglas.correo_invalido("a@canella.com.gt") is None


def test_eml_es_borrador_con_adjuntos():
    crudo = reglas.correo_eml("a@x.com", "b@x.com", "Asunto ñ", "Cuerpo", [reglas.Adjunto("51595_X.pdf", b"%PDF-1")])
    m = email.message_from_bytes(crudo, policy=policy.default)
    assert m["X-Unsent"] == "1" and m["To"] == "a@x.com" and m["Cc"] == "b@x.com" and m["Subject"] == "Asunto ñ"
    assert [a.get_filename() for a in m.iter_attachments()] == ["51595_X.pdf"]


# ======================================================================== documentos

def test_armar_toma_las_paginas_en_orden_y_antepone_la_factura():
    from app.modulos.expedientes_seguros import documentos
    original = pdf(5)
    assert anchos(documentos.armar(original, [2, 5])) == [613, 616]
    assert anchos(documentos.armar(original, [1], anteponer=pdf(1, ancho=500))) == [500, 612]
    with pytest.raises(IndexError):
        documentos.armar(original, [6])
    with pytest.raises(documentos.PdfInvalido):
        documentos.contar_paginas(b"no es pdf")


def test_leer_archivo_inexistente_da_file_not_found(tmp_path):
    from app.modulos.expedientes_seguros import documentos
    with pytest.raises(FileNotFoundError):
        documentos.leer(tmp_path / "no_existe.pdf")


def test_concatenar_junta_todas_las_paginas_de_cada_pieza_en_orden():
    from app.modulos.expedientes_seguros import documentos
    assert anchos(documentos.concatenar([pdf(2, ancho=500), pdf(1, ancho=700)])) == [500, 501, 700]


def test_imagen_de_pagina_es_jpeg():
    from app.modulos.expedientes_seguros import documentos
    jpg = documentos.imagen_pagina(pdf(2), 2, 120)
    assert jpg[:3] == b"\xff\xd8\xff"
    with pytest.raises(IndexError):
        documentos.imagen_pagina(pdf(2), 3)


# ======================================================================= pantallas

class SapFalso:
    def __init__(self):
        self.llamadas = {}
        self.bandeja = []
        self.consultas = 0
        self.caido = False

    def pendientes(self, ceco):
        if self.caido:
            raise SapNoDisponible("sin red")
        return [p for p in self.bandeja if p.expediente]

    def buscar_llamada(self, call_id):
        self.consultas += 1
        if self.caido:
            raise SapNoDisponible("sin red")
        return self.llamadas.get(call_id)


@pytest.fixture
def entorno(app, tmp_path, monkeypatch):
    sap = SapFalso()
    ruta = tmp_path / "51595.pdf"
    ruta.write_bytes(pdf(6))
    sap.llamadas[51595] = Llamada(
        call_id=51595, orden=100129274, aseguradora_codigo="C000078", aseguradora_nombre="ASEGURADORA LA CEIBA, S. A.",
        reclamo="202604763", poliza="0224103497-14", ceco="1602", ceco_nombre="SERVICIOS AUTO TALLER PINTURA",
        anexos=(Anexo(1, str(ruta), "51595.pdf", None),), factura=Factura(55, "E4C46263", "3713157398"),
    )
    sap.llamadas[1] = Llamada(1, 1, "C999", "OTRA", "", "", "1602", "", (), None)
    monkeypatch.setattr(servicios, "crear_repositorio", lambda: sap)
    monkeypatch.setattr(servicios, "_anexos", {})
    app.instance_path = str(tmp_path / "instance")
    for clave, valor in {
        "para": "gestrada@canella.com.gt; cobroscanella@canella.com.gt", "cc": "ctoledo@canella.com.gt",
        "asunto": "{aseguradora}//Serie: {serie} Número: {numero}//CANELLA",
        "cuerpo": "Adjunto documentos y factura Serie: {serie} Número: {numero}",
    }.items():
        db.session.add(Parametro(clave=clave, valor=valor))
    db.session.commit()
    return sap


@pytest.fixture
def cajero(entrar_como):
    return entrar_como(crear_usuario("cajero", modulos=["expedientes_seguros"]))


def test_sin_permiso_no_ve_ni_las_imagenes(entorno, entrar_como):
    c = entrar_como(crear_usuario("otro"))
    assert c.get("/m/expedientes_seguros/").status_code == 403
    assert c.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/1.jpg").status_code == 403


def test_visor_muestra_miniaturas_y_correo_sugerido(entorno, cajero):
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert "Expediente: 6 páginas" in html and html.count('name="paginas"') == 6
    assert "ASEGURADORA LA CEIBA, S. A.//Serie: E4C46263 Número: 3713157398//CANELLA" in html
    assert "51595_ASEGURADORA LA CEIBA, S. A_" in html
    assert 'class="col-auto align-self-end encabezado-origen">' in html and "logo-sap-grande" in html   # SAP, primero
    r = cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/3.jpg")
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    antes = entorno.consultas
    cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/4.jpg?tamano=ampliada")
    assert entorno.consultas == antes                        # la ruta del anexo queda recordada
    assert cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/9.jpg").status_code == 404


@pytest.mark.parametrize("url, mensaje", [
    ("/m/expedientes_seguros/llamadas/777?ceco=1602", "no existe en SAP"),
    ("/m/expedientes_seguros/llamadas/51595?ceco=1101", "no pertenece al centro de costo 1101"),
    ("/m/expedientes_seguros/llamadas/1?ceco=1602", "no tiene el expediente en PDF"),
])
def test_busquedas_que_no_abren_el_visor(entorno, cajero, url, mensaje):
    r = cajero.get(url, follow_redirects=True)
    assert mensaje in r.get_data(as_text=True)


def test_sap_caido_avisa_sin_error_500(entorno, cajero):
    entorno.caido = True
    r = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602", follow_redirects=True)
    assert r.status_code == 200 and "No se pudo consultar SAP" in r.get_data(as_text=True)


def datos_formulario(**cambios):
    datos = {"ceco": "1602", "paginas": ["2", "4", "5"], "serie": "E4C46263", "numero": "3713157398",
             "para": "gestrada@canella.com.gt", "cc": "", "asunto": "LA CEIBA//Serie", "cuerpo": "Adjunto", "abierto_en": "1"}
    datos.update(cambios)
    return datos


def test_generar_paquete_registra_y_prepara_descargas(entorno, cajero):
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    assert r.status_code == 302
    p = Paquete.query.one()
    assert (p.call_id, p.paginas, p.cantidad_paginas, p.total_paginas, p.aseguradora_codigo) == (51595, "2, 4-5", 3, 6, "C000078")
    assert p.nombre_archivo == reglas.nombre_paquete(51595, "ASEGURADORA LA CEIBA, S. A.", date.today())

    descarga = cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}/archivos/{p.nombre_archivo}")
    assert descarga.status_code == 200 and anchos(descarga.data) == [613, 615, 616]
    eml = email.message_from_bytes(cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}/correo.eml").data, policy=policy.default)
    assert eml["X-Unsent"] == "1" and eml["To"] == "gestrada@canella.com.gt"
    assert [a.get_filename() for a in eml.iter_attachments()] == [p.nombre_archivo]
    assert cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}/archivos/..%2F..%2Fsecreto.pdf").status_code == 404


def test_factura_unida_o_separada(entorno, cajero):
    factura = (io.BytesIO(pdf(1, ancho=500)), "factura.pdf")
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario(factura=factura),
                content_type="multipart/form-data")
    unida = Paquete.query.one()
    assert anchos(servicios.adjuntos_de(unida)[0].contenido)[0] == 500 and len(servicios.adjuntos_de(unida)) == 1

    factura = (io.BytesIO(pdf(1, ancho=500)), "factura.pdf")
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario(factura=factura, factura_separada="1"),
                content_type="multipart/form-data")
    separada = Paquete.query.order_by(Paquete.id.desc()).first()
    nombres = [a.nombre for a in servicios.adjuntos_de(separada)]
    assert nombres == [separada.nombre_archivo, "FAC 51595-ASEGURADORA LA CEIBA, S. A.pdf"]


@pytest.mark.parametrize("cambios, mensaje", [
    ({"paginas": []}, "Selecciona al menos una página"),
    ({"serie": ""}, "Falta la Serie o el Número"),
    ({"para": ""}, "al menos un destinatario"),
    ({"cc": "malo@"}, "«malo@» no es válida"),
    ({"asunto": ""}, "El asunto está vacío"),
])
def test_validaciones_antes_de_generar(entorno, cajero, cambios, mensaje):
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario(**cambios))
    assert r.status_code == 422 and mensaje in r.get_data(as_text=True)
    assert Paquete.query.count() == 0


def test_factura_que_no_es_pdf(entorno, cajero):
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", content_type="multipart/form-data",
                    data=datos_formulario(factura=(io.BytesIO(b"hola"), "f.pdf")))
    assert r.status_code == 422 and "no es un PDF válido" in r.get_data(as_text=True)


def test_factura_supera_el_limite(entorno, cajero):
    from app.modulos.expedientes_seguros.views import MAX_FACTURA_BYTES
    grande = io.BytesIO(b"%" * (MAX_FACTURA_BYTES + 1))
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", content_type="multipart/form-data",
                    data=datos_formulario(factura=(grande, "f.pdf")))
    assert r.status_code == 422 and "supera 20 MB" in r.get_data(as_text=True)
    assert Paquete.query.count() == 0


def test_generar_en_llamada_inexistente_redirige(entorno, cajero):
    r = cajero.post("/m/expedientes_seguros/llamadas/999999/paquetes", data=datos_formulario(), follow_redirects=True)
    assert "no existe en SAP" in r.get_data(as_text=True)
    assert Paquete.query.count() == 0


def test_buscar_sin_numero_avisa(entorno, cajero):
    r = cajero.get("/m/expedientes_seguros/buscar?llamada=&ceco=1602", follow_redirects=True)
    assert "Escribe el número de la llamada" in r.get_data(as_text=True)


def test_buscar_redirige_al_visor(entorno, cajero):
    r = cajero.get("/m/expedientes_seguros/buscar?llamada=51595&ceco=1602")
    assert r.status_code == 302 and "/llamadas/51595" in r.headers["Location"]


def test_correo_eml_404_si_ya_no_hay_archivos(entorno, cajero, monkeypatch):
    """Si los archivos del paquete ya se purgaron (retención vencida), el .eml también deja de
    existir: no hay nada que adjuntar."""
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    p = Paquete.query.one()
    monkeypatch.setenv("EXPEDIENTES_RETENCION_DIAS", "0")
    p.creado_en = p.creado_en.replace(year=p.creado_en.year - 1)
    db.session.commit()
    servicios.purgar_antiguos()
    assert cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}/correo.eml").status_code == 404


def test_miniatura_de_linea_inexistente_da_404(entorno, cajero):
    cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602")   # calienta la caché de anexos
    assert cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/99/paginas/1.jpg").status_code == 404


def test_miniatura_con_sap_caido_da_503(entorno, cajero):
    cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602")   # calienta la caché de anexos
    entorno.caido = True
    servicios._anexos.clear()   # fuerza a volver a consultar SAP (ahora caído)
    r = cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/1.jpg")
    assert r.status_code == 503


def test_ruta_anexo_sin_cache_vuelve_a_consultar_sap(entorno, cajero):
    """ruta_anexo recuerda la ruta una hora; sin eso (caché vencida o en frío), vuelve a SAP."""
    servicios._anexos.clear()
    r = cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/1.jpg")
    assert r.status_code == 200


def test_miniatura_ya_generada_no_se_rehace(entorno, cajero, monkeypatch):
    r1 = cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/1.jpg")
    assert r1.status_code == 200
    from app.modulos.expedientes_seguros import documentos as documentos_mod
    monkeypatch.setattr(documentos_mod, "imagen_pagina",
                         lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debía regenerarla")))
    r2 = cajero.get("/m/expedientes_seguros/llamadas/51595/anexos/1/paginas/1.jpg")
    assert r2.status_code == 200 and r2.data == r1.data


def test_modulo_sin_configurar_avisa_en_bandeja_y_en_visor(cajero, monkeypatch):
    """Sin SAP configurado (variables EXPEDIENTES_SAP_* faltantes), ni la bandeja ni el visor
    deben intentar conectarse: se avisa con el motivo exacto. No usa ``entorno`` a propósito:
    aquí se reemplaza crear_repositorio() mismo, nunca configuracion.sap() (evita cualquier
    intento real de conexión a SAP si el .env de desarrollo tuviera credenciales)."""
    from app.modulos.expedientes_seguros import configuracion as config_mod

    def falla():
        raise config_mod.ConfiguracionIncompleta("Faltan variables en .env: EXPEDIENTES_SAP_SERVIDOR")
    monkeypatch.setattr(servicios, "crear_repositorio", falla)

    assert "módulo no está configurado" in cajero.get(
        "/m/expedientes_seguros/llamadas/51595?ceco=1602", follow_redirects=True).get_data(as_text=True)
    html_inicio = cajero.get("/m/expedientes_seguros/").get_data(as_text=True)
    assert "Faltan variables en .env: EXPEDIENTES_SAP_SERVIDOR" in html_inicio


def test_anexo_no_es_un_pdf_valido(entorno, cajero):
    ruta = entorno.llamadas[51595].anexos[0].ruta
    with open(ruta, "wb") as f:
        f.write(b"no es un pdf")
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602", follow_redirects=True).get_data(as_text=True)
    assert "no es un PDF válido" in html


def test_anexo_no_existe_en_el_servidor_de_archivos(entorno, cajero):
    ruta = entorno.llamadas[51595].anexos[0].ruta
    os.remove(ruta)
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602", follow_redirects=True).get_data(as_text=True)
    assert "no se pudo abrir en el servidor de archivos" in html


def test_plantilla_de_la_aseguradora_y_campos_por_defecto(entorno, cajero):
    ceiba = Aseguradora(nombre="CEIBA", asunto="CEIBA {reclamo}")
    ceiba.codigos.append(CodigoAseguradora(codigo="C000078"))
    # «Archivo aparte» se decide por fila del checklist, no por la aseguradora (ver Documento.separado).
    ceiba.documentos.append(Documento(orden=1, nombre="Factura original", obligatorio=True, separado=True))
    db.session.add(ceiba)
    db.session.commit()
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert 'value="CEIBA 202604763"' in html                  # asunto propio
    assert "gestrada@canella.com.gt; cobroscanella@canella.com.gt" in html   # "Para" por defecto
    assert 'name="factura_separada" value="1" checked' in html


def test_archivos_vencidos_se_borran_y_el_registro_queda(entorno, cajero, monkeypatch):
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    p = Paquete.query.one()
    monkeypatch.setenv("EXPEDIENTES_RETENCION_DIAS", "0")
    p.creado_en = p.creado_en.replace(year=p.creado_en.year - 1)
    db.session.commit()
    assert servicios.purgar_antiguos() == 1
    html = cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}").get_data(as_text=True)
    assert "Los archivos se borraron" in html and Paquete.query.count() == 1


# ================================================================== configuración

def test_aseguradoras_solo_administradores(entorno, cajero, entrar_como):
    assert cajero.get("/m/expedientes_seguros/aseguradoras").status_code == 200
    assert cajero.get("/m/expedientes_seguros/aseguradoras/nueva").status_code == 403
    assert cajero.post("/m/expedientes_seguros/correo-por-defecto", data={}).status_code == 403


def test_admin_crea_aseguradora_con_dos_codigos(entorno, entrar_como):
    from app.core.models import Usuario
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    r = c.post("/m/expedientes_seguros/aseguradoras/nueva",
               data={"nombre": "MAPFRE", "codigos": "c000347, C009999", "activa": "y"})
    assert r.status_code == 302
    mapfre = Aseguradora.query.filter_by(nombre="MAPFRE").one()
    # Recién creada, sin checklist: «archivo aparte» se configura ahí, no al crear la aseguradora.
    assert mapfre.lista_codigos == "C000347, C009999" and not mapfre.factura_separada
    r = c.post("/m/expedientes_seguros/aseguradoras/nueva", data={"nombre": "OTRA", "codigos": "C000347"})
    assert "ya es de MAPFRE" in r.get_data(as_text=True)
    r = c.post("/m/expedientes_seguros/aseguradoras/nueva", data={"nombre": "OTRA", "codigos": "no! válido"})
    assert "no es un código válido" in r.get_data(as_text=True)
    r = c.post("/m/expedientes_seguros/aseguradoras/nueva", data={"nombre": "OTRA", "codigos": "C1", "para": "malo@"})
    assert "«malo@» no es válida" in r.get_data(as_text=True)


def test_admin_edita_aseguradora(entorno, entrar_como):
    from app.core.models import Usuario
    ceiba = Aseguradora(nombre="CEIBA", activa=True)
    ceiba.codigos.append(CodigoAseguradora(codigo="C000078"))
    db.session.add(ceiba)
    db.session.commit()
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))

    assert 'value="C000078"' in c.get(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}").get_data(as_text=True)

    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}",
               data={"nombre": "LA CEIBA", "codigos": "C000078, C000099", "para": "nuevo@canella.com.gt"})
    assert r.status_code == 302
    db.session.expire_all()
    ceiba = db.session.get(Aseguradora, ceiba.id)
    assert ceiba.nombre == "LA CEIBA" and ceiba.lista_codigos == "C000078, C000099" and ceiba.para == "nuevo@canella.com.gt"

    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}",
               data={"nombre": "LA CEIBA", "codigos": "C000078", "cc": "malo@"})
    assert "«malo@» no es válida" in r.get_data(as_text=True)

    # Nombre repetido con otra aseguradora: se rechaza (consigo misma sí se permite, es la misma fila).
    otra = Aseguradora(nombre="OTRA")
    db.session.add(otra)
    db.session.commit()
    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}", data={"nombre": "OTRA", "codigos": "C000078"})
    assert "Ya existe una aseguradora con ese nombre" in r.get_data(as_text=True)
    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}", data={"nombre": "LA CEIBA", "codigos": "C000078"})
    assert r.status_code == 302   # el propio nombre no se rechaza a sí mismo


def test_eliminar_aseguradora_bloqueada_si_tiene_paquetes(ceiba_con_checklist, cajero, entrar_como):
    from app.core.models import Usuario
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    ceiba = Aseguradora.query.filter_by(nombre="CEIBA").one()
    cajero.post("/salir")
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}/eliminar", follow_redirects=True)
    assert "tiene 1 paquete(s) registrados" in r.get_data(as_text=True)
    assert Aseguradora.query.filter_by(nombre="CEIBA").count() == 1


def test_eliminar_aseguradora_sin_paquetes(entorno, entrar_como):
    from app.core.models import Usuario
    ceiba = Aseguradora(nombre="CEIBA")
    ceiba.codigos.append(CodigoAseguradora(codigo="C000078"))
    db.session.add(ceiba)
    db.session.commit()
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}/eliminar", follow_redirects=True)
    assert "eliminada" in r.get_data(as_text=True)
    assert Aseguradora.query.filter_by(nombre="CEIBA").count() == 0


def test_admin_actualiza_correo_por_defecto(entorno, entrar_como):
    from app.core.models import Usuario
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    r = c.post("/m/expedientes_seguros/correo-por-defecto",
               data={"para": "nuevo@canella.com.gt", "cc": "", "asunto": "Nuevo asunto", "cuerpo": "Nuevo cuerpo"})
    assert r.status_code == 302
    assert servicios.parametros()["asunto"] == "Nuevo asunto"

    r = c.post("/m/expedientes_seguros/correo-por-defecto",
               data={"para": "malo@", "asunto": "x", "cuerpo": "x"})
    assert "«malo@» no es válida" in r.get_data(as_text=True)
    r = c.post("/m/expedientes_seguros/correo-por-defecto",
               data={"para": "a@canella.com.gt", "cc": "malo@", "asunto": "x", "cuerpo": "x"})
    assert "«malo@» no es válida" in r.get_data(as_text=True)


def test_lista_de_aseguradoras_sin_n_mas_1(entorno, entrar_como):
    """La plantilla lee `codigos` y `documentos` de cada fila: sin selectinload, cada aseguradora
    dispara sus propias consultas y el número crece con la cantidad de aseguradoras (N+1)."""
    from app.core.models import Usuario
    for i in range(8):
        a = Aseguradora(nombre=f"ASEGURADORA {i}")
        a.codigos.append(CodigoAseguradora(codigo=f"C{i:06d}"))
        a.documentos.append(Documento(orden=1, nombre="Factura original", obligatorio=True))
        db.session.add(a)
    db.session.commit()
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    with contar_consultas() as n:
        r = c.get("/m/expedientes_seguros/aseguradoras")
    assert r.status_code == 200
    # Fijo (aseguradoras + un IN para codigos + un IN para documentos + permisos/menú/parámetros),
    # no uno por fila: sin el selectinload serían ~18 para 8 aseguradoras (2N+2), no menos de 10.
    assert n[0] <= 10, f"{n[0]} consultas para 8 aseguradoras: parece un N+1"


def test_ruta_accesible_cambia_el_servidor_de_la_ruta_unc():
    ruta = r"\\Srv-sapcanella\archivos-sap\Documentos_SAP\51595.pdf"
    assert reglas.ruta_accesible(ruta, "128.1.200.50") == r"\\128.1.200.50\archivos-sap\Documentos_SAP\51595.pdf"
    assert reglas.ruta_accesible(ruta, "") == ruta
    assert reglas.ruta_accesible(r"C:\x\a.pdf", "128.1.200.50") == r"C:\x\a.pdf"


# ======================================================================= bandeja

def test_bandeja_excluye_las_armadas_y_marca_la_antiguedad(entorno, cajero, monkeypatch):
    hoy = date.today()
    entorno.bandeja = [
        Pendiente(40000, "C000347", "MAPFRE SEGUROS", "1", hoy - timedelta(days=90), hoy - timedelta(days=80)),
        Pendiente(51595, "C000078", "ASEGURADORA LA CEIBA, S. A.", "202604763", hoy - timedelta(days=5), hoy - timedelta(days=1)),
        Pendiente(51602, "C000347", "MAPFRE SEGUROS", "88213", hoy - timedelta(days=2), hoy - timedelta(days=2)),
        Pendiente(51610, "C000347", "MAPFRE SEGUROS", "88300", hoy, hoy),
    ]
    filas = servicios.bandeja("1602")
    # Todas las activas, sin ventana de días; la antigüedad cuenta desde que se abrió la llamada.
    assert [(f.pendiente.call_id, f.dias, f.color) for f in filas] == [
        (40000, 90, "red"), (51595, 5, "red"), (51602, 2, "yellow"), (51610, 0, "green")]
    entorno.bandeja = entorno.bandeja[1:]

    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    assert [f.pendiente.call_id for f in servicios.bandeja("1602")] == [51602, 51610]

    html = cajero.get("/m/expedientes_seguros/").get_data(as_text=True)
    assert "Pendientes de armar" in html and '<td class="fw-bold">51602</td>' in html
    assert '<td class="fw-bold">51595</td>' not in html and 'fw-bold me-2">51595</span>' in html   # pasó a "Armados hoy"
    assert "Armados hoy" in html and "hace 2 días" in html and "hoy" in html
    filtrado = cajero.get("/m/expedientes_seguros/?aseguradora=C000078").get_data(as_text=True)
    assert "No hay llamadas activas pendientes de ese cliente" in filtrado


def test_bandeja_con_sap_caido_no_rompe_el_inicio(entorno, cajero):
    entorno.caido = True
    r = cajero.get("/m/expedientes_seguros/")
    assert r.status_code == 200 and "No se pudo consultar SAP para la bandeja" in r.get_data(as_text=True)


def test_historial_pagina(entorno, cajero):
    assert cajero.get("/m/expedientes_seguros/paquetes").status_code == 200



# ======================================================================= checklist

def test_reglas_del_checklist():
    assert reglas.es_factura("Factura  ORIGINAL") and not reglas.es_factura("Facturas de repuestos")
    documentos = [{"id": 1, "nombre": "Factura original", "obligatorio": True},
                  {"id": 2, "nombre": "Finiquito", "obligatorio": True},
                  {"id": 3, "nombre": "Encuesta", "obligatorio": False},
                  {"id": 4, "nombre": "DPI", "obligatorio": True}]
    # Página 5 asignada al DPI pero no marcada: no cuenta.
    estado = reglas.evaluar_checklist(documentos, {2: 2, 3: 2, 5: 4}, [2, 3], con_factura=True)
    assert [(d["documento"], d["presente"], d["paginas"]) for d in estado] == [
        ("Factura original", True, ""), ("Finiquito", True, "2-3"), ("Encuesta", False, ""), ("DPI", False, "")]
    assert reglas.faltantes(estado) == ["DPI"]


@pytest.fixture
def ceiba_con_checklist(entorno):
    ceiba = Aseguradora(nombre="CEIBA")
    ceiba.codigos.append(CodigoAseguradora(codigo="C000078"))
    ceiba.documentos = [Documento(orden=1, nombre="Factura original", obligatorio=True),
                        Documento(orden=2, nombre="Finiquito (asegurado/tercero)", obligatorio=True),
                        Documento(orden=3, nombre="Encuesta", obligatorio=False)]
    db.session.add(ceiba)
    db.session.commit()
    return {d.nombre: d.id for d in ceiba.documentos}


def test_visor_muestra_el_checklist_de_la_aseguradora(ceiba_con_checklist, cajero):
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert html.count("data-avance-porcentaje") == 2       # mismo componente en el panel y en la vista grande
    assert html.count('title="ASEGURADORA LA CEIBA, S. A."') == 2   # nombre en una línea, completo en el tooltip
    assert f'data-documento="{ceiba_con_checklist["Finiquito (asegurado/tercero)"]}" data-obligatorio="1"' in html
    encuesta = ceiba_con_checklist["Encuesta"]
    assert f'data-documento="{encuesta}" data-obligatorio="0"' in html and 'data-nombre="Encuesta"' in html
    assert 'id="modal-checklist"' in html and 'id="modal-pagina-marcar"' not in html and 'id="modal-pagina-igual"' in html and 'id="modal-pagina-posicion"' in html
    assert 'id="modal-pagina-documento"' not in html and html.count('class="pagina-doc"') == 6


def test_el_paquete_guarda_el_checklist_como_evidencia(ceiba_con_checklist, cajero):
    finiquito = ceiba_con_checklist["Finiquito (asegurado/tercero)"]
    datos = datos_formulario(paginas=["2", "3"], **{"doc_2": str(finiquito), "doc_3": str(finiquito),
                                                     "doc_4": "999999", "doc_5": str(finiquito)})
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos)
    p = Paquete.query.one()
    estado = servicios.checklist_de(p)
    assert [(d["documento"], d["presente"], d["paginas"]) for d in estado] == [
        ("Factura original", False, ""), ("Finiquito (asegurado/tercero)", True, "2-3"), ("Encuesta", False, "")]
    html = cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}").get_data(as_text=True)
    assert "Checklist al generar" in html and "pág. 2-3" in html and "Faltó" in html


def test_documento_del_checklist_en_archivo_aparte(ceiba_con_checklist, cajero):
    """Un documento marcado «archivo aparte» sale en su propio PDF, con sus páginas (y las
    comparte con el principal si alguna de esas páginas también está asignada a un documento que
    sí va unido: se copia, no se recorta en exclusiva — ver reglas.separar_por_documento)."""
    finiquito_id = ceiba_con_checklist["Finiquito (asegurado/tercero)"]
    finiquito = db.session.get(Documento, finiquito_id)
    finiquito.separado = True
    db.session.commit()

    # Página 2 (ancho 613): solo Finiquito (aparte) → sale solo en su propio archivo.
    # Página 3 (ancho 614): Finiquito (aparte) y Encuesta (unida) → sale en los dos.
    # Página 4 (ancho 615): sin documento → solo en el principal.
    encuesta_id = ceiba_con_checklist["Encuesta"]
    datos = datos_formulario(paginas=["2", "3", "4"], **{
        "doc_2": str(finiquito_id), "doc_3": f"{finiquito_id},{encuesta_id}",
    })
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos)
    assert r.status_code == 302
    p = Paquete.query.one()

    adjuntos = {a.nombre: a for a in servicios.adjuntos_de(p)}
    nombre_aparte = reglas.nombre_documento_separado(51595, "ASEGURADORA LA CEIBA, S. A.", "Finiquito (asegurado/tercero)")
    assert set(adjuntos) == {p.nombre_archivo, nombre_aparte}
    assert anchos(adjuntos[p.nombre_archivo].contenido) == [614, 615]           # páginas 3 y 4
    assert anchos(adjuntos[nombre_aparte].contenido) == [613, 614]              # páginas 2 y 3

    # El correo real (la ruta que abre Caja en Outlook) trae los dos como adjuntos distintos.
    eml = email.message_from_bytes(cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}/correo.eml").data, policy=policy.default)
    assert {a.get_filename() for a in eml.iter_attachments()} == {p.nombre_archivo, nombre_aparte}


def test_si_falla_un_archivo_aparte_no_queda_nada_a_medias(ceiba_con_checklist, cajero, monkeypatch):
    """Si falla escribir un documento «aparte» a medio armar (disco lleno, permisos...), no debe
    quedar ni la carpeta con archivos sueltos ni la fila del paquete: si quedara la carpeta sin su
    fila, purgar_antiguos() nunca la encontraría y los datos personales no se borrarían nunca."""
    finiquito_id = ceiba_con_checklist["Finiquito (asegurado/tercero)"]
    finiquito = db.session.get(Documento, finiquito_id)
    finiquito.separado = True
    db.session.commit()

    from app.modulos.expedientes_seguros import servicios as mod
    monkeypatch.setattr(mod.reglas, "nombre_documento_separado",
                         lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disco lleno (simulado)")))

    carpeta_paquetes = servicios.directorio_trabajo() / "paquetes"
    antes = set(carpeta_paquetes.iterdir()) if carpeta_paquetes.exists() else set()

    datos = datos_formulario(paginas=["2"], **{"doc_2": str(finiquito_id)})
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos)
    assert r.status_code == 500
    assert Paquete.query.count() == 0
    despues = set(carpeta_paquetes.iterdir()) if carpeta_paquetes.exists() else set()
    assert despues == antes


def test_sin_checklist_configurado_lo_avisa(entorno, cajero):
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert "no tiene checklist configurado" in html


def test_editor_del_checklist(ceiba_con_checklist, entrar_como, cajero):
    from app.core.models import Usuario
    ids = ceiba_con_checklist
    ceiba = Aseguradora.query.filter_by(nombre="CEIBA").one()
    url = f"/m/expedientes_seguros/aseguradoras/{ceiba.id}/checklist"
    assert cajero.get(url).status_code == 403                       # solo administradores
    cajero.post("/salir")

    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    html = c.get(url).get_data(as_text=True)
    assert 'value="Finiquito (asegurado/tercero)"' in html and 'id="plantilla-fila"' in html

    fac, fin, enc = (str(ids[n]) for n in ("Factura original", "Finiquito (asegurado/tercero)", "Encuesta"))
    datos = {
        # nuevo orden: Finiquito, Factura (editada: aparte), DPI (nuevo, n1); Encuesta se quita
        "orden": [fin, fac, "n1", enc],
        f"nombre-{fin}": "Finiquito", f"obligatorio-{fin}": "1", f"activo-{fin}": "1",
        f"nombre-{fac}": "Factura original", f"obligatorio-{fac}": "1", f"separado-{fac}": "1",   # inactiva (sin activo)
        "nombre-n1": "  Copia de   DPI ", "obligatorio-n1": "1", "activo-n1": "1",
        f"nombre-{enc}": "Encuesta", f"activo-{enc}": "1", f"quitar-{enc}": "1",
    }
    assert c.post(url, data=datos).status_code == 302
    db.session.expire_all()
    ceiba = Aseguradora.query.filter_by(nombre="CEIBA").one()
    assert [(d.orden, d.nombre, d.obligatorio, d.activo, d.separado) for d in ceiba.documentos] == [
        (1, "Finiquito", True, True, False), (2, "Factura original", True, False, True), (3, "Copia de DPI", True, True, False)]
    assert ceiba.documentos[0].id == int(fin)                         # se editó, no se recreó
    # La aseguradora no vuelve a tener su propia bandera: la deriva de la fila «Factura original».
    assert ceiba.factura_separada is True

    # El visor solo muestra los activos.
    visor = c.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert 'data-nombre="Copia de DPI"' in visor and 'data-nombre="Factura original"' not in visor


@pytest.mark.parametrize("datos, mensaje", [
    ({"orden": ["n1"], "nombre-n1": ""}, "no tiene nombre"),
    ({"orden": ["n1", "n2"], "nombre-n1": "DPI", "nombre-n2": "dpi"}, "está repetido"),
])
def test_editor_del_checklist_valida(ceiba_con_checklist, entrar_como, datos, mensaje):
    from app.core.models import Usuario
    ceiba = Aseguradora.query.filter_by(nombre="CEIBA").one()
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    r = c.post(f"/m/expedientes_seguros/aseguradoras/{ceiba.id}/checklist", data=datos)
    assert r.status_code == 422 and mensaje in r.get_data(as_text=True)
    assert len(Aseguradora.query.filter_by(nombre="CEIBA").one().documentos) == 3     # nada cambió



def test_bandeja_muestra_todas_las_activas_sin_ventana_de_dias(entorno):
    hoy = date.today()
    entorno.bandeja = [Pendiente(1, "C", "X", "", hoy - timedelta(days=400), hoy - timedelta(days=3)),
                       Pendiente(2, "C", "X", "", hoy - timedelta(days=1), hoy),
                       Pendiente(3, "C", "X", "", hoy, hoy)]
    assert [f.pendiente.call_id for f in servicios.bandeja("1602")] == [1, 2, 3]


def test_varias_facturas_se_elige_la_de_la_aseguradora(entorno, cajero):
    ruta = entorno.llamadas[51595].anexos[0].ruta
    deducible = Factura(70, "AAAA0001", "111", date(2026, 9, 20), "JUAN PEREZ", False)
    aseguradora = Factura(71, "E4C46263", "3713157398", date(2026, 9, 21), "ASEGURADORA LA CEIBA, S. A.", True)
    entorno.llamadas[51595] = Llamada(
        51595, 100129274, "C000078", "ASEGURADORA LA CEIBA, S. A.", "202604763", "0224103497-14", "1602", "",
        (Anexo(1, ruta, "51595.pdf", None),), aseguradora, (aseguradora, deducible))
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert 'id="factura-sap"' in html and "(no es la aseguradora)" in html
    assert 'name="serie" value="E4C46263"' in html and 'data-serie="AAAA0001"' in html


def test_solo_facturas_de_otro_cliente_avisa(entorno, cajero):
    ruta = entorno.llamadas[51595].anexos[0].ruta
    deducible = Factura(70, "AAAA0001", "111", date(2026, 9, 20), "JUAN PEREZ", False)
    entorno.llamadas[51595] = Llamada(
        51595, 1, "C000078", "ASEGURADORA LA CEIBA, S. A.", "", "", "1602", "",
        (Anexo(1, ruta, "51595.pdf", None),), None, (deducible,))
    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert "no son de la aseguradora" in html and 'name="serie" value=""' in html


def test_el_dpi_a_color_se_combina_con_el_expediente(entorno, tmp_path, cajero):
    """La llamada puede traer, además del expediente, un segundo anexo en SAP con el DPI a color
    (mismo origen que el expediente, pero archivo aparte: confirmado en ATC1 real, ver
    reglas.es_dpi). El visor combina las páginas de los dos como si fueran un solo documento, y el
    paquete puede tomar hojas de cualquiera para el PDF final."""
    ruta_dpi = tmp_path / "dpi.pdf"
    ruta_dpi.write_bytes(pdf(1, ancho=700))
    original = entorno.llamadas[51595]
    entorno.llamadas[51595] = Llamada(
        original.call_id, original.orden, original.aseguradora_codigo, original.aseguradora_nombre,
        original.reclamo, original.poliza, original.ceco, original.ceco_nombre,
        original.anexos + (Anexo(2, str(ruta_dpi), "DPI P-123ABC, LLAMADA 51595, RECLAMO 1.pdf", None),),
        original.factura, original.facturas,
    )

    html = cajero.get("/m/expedientes_seguros/llamadas/51595?ceco=1602").get_data(as_text=True)
    assert "Expediente: 7 páginas" in html   # 6 del expediente + 1 del DPI
    assert "DPI P-123ABC" in html and "rejilla-seccion-titulo" in html

    datos = datos_formulario(paginas=["4", "7"])   # página 4 del expediente, 7 = la única del DPI
    r = cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos)
    assert r.status_code == 302
    p = Paquete.query.one()
    assert anchos(servicios.adjuntos_de(p)[0].contenido) == [615, 700]
    assert p.anexo_dpi == str(ruta_dpi) and p.anexo_dpi_sha256


def test_sin_dpi_no_hay_evidencia_de_dpi(entorno, cajero):
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    p = Paquete.query.one()
    assert p.anexo_dpi is None and p.anexo_dpi_sha256 is None


def test_campos_fel_confirmados_por_defecto(monkeypatch):
    """Confirmado en SBO_CANELLA el 28/09/2026: llamada 68267 → factura 3151202 de MAPFRE,
    Serie 87BC5934 en U_DoctoSerie y Número 3581693582 en U_DoctoNo (los del correo real)."""
    for n, v in {"EXPEDIENTES_SAP_SERVIDOR": "s", "EXPEDIENTES_SAP_BASE": "b", "EXPEDIENTES_SAP_USUARIO": "u",
                 "EXPEDIENTES_SAP_CONTRASENA": "c"}.items():
        monkeypatch.setenv(n, v)
    monkeypatch.delenv("EXPEDIENTES_SAP_CAMPO_SERIE", raising=False)
    monkeypatch.delenv("EXPEDIENTES_SAP_CAMPO_NUMERO", raising=False)
    config = configuracion.sap()
    assert (config.campo_serie, config.campo_numero) == ("U_DoctoSerie", "U_DoctoNo")


def test_sap_sin_variables_lanza_configuracion_incompleta(monkeypatch):
    for n in ("EXPEDIENTES_SAP_SERVIDOR", "EXPEDIENTES_SAP_BASE", "EXPEDIENTES_SAP_USUARIO", "EXPEDIENTES_SAP_CONTRASENA"):
        monkeypatch.delenv(n, raising=False)
    with pytest.raises(configuracion.ConfiguracionIncompleta, match="EXPEDIENTES_SAP_SERVIDOR"):
        configuracion.sap()


def test_campo_fel_invalido_se_rechaza(monkeypatch):
    """campo_serie/campo_numero van dentro del SQL (nombre de columna): se valida que sea un
    identificador, no cualquier texto, para no abrir paso a inyección por una variable mal puesta."""
    for n, v in {"EXPEDIENTES_SAP_SERVIDOR": "s", "EXPEDIENTES_SAP_BASE": "b", "EXPEDIENTES_SAP_USUARIO": "u",
                 "EXPEDIENTES_SAP_CONTRASENA": "c"}.items():
        monkeypatch.setenv(n, v)
    monkeypatch.setenv("EXPEDIENTES_SAP_CAMPO_SERIE", "U_Serie; DROP TABLE OSCL")
    with pytest.raises(configuracion.ConfiguracionIncompleta, match="no es un nombre de columna válido"):
        configuracion.sap()


def test_una_pagina_puede_tener_varios_documentos(ceiba_con_checklist, cajero):
    """DPI y tarjeta de circulación suelen venir en la misma hoja: una página, dos documentos."""
    finiquito, encuesta = ceiba_con_checklist["Finiquito (asegurado/tercero)"], ceiba_con_checklist["Encuesta"]
    assert reglas.evaluar_checklist([{"id": 1, "nombre": "A", "obligatorio": True}, {"id": 2, "nombre": "B", "obligatorio": True}],
                                    {4: [1, 2]}, [4], con_factura=False)[1]["paginas"] == "4"
    datos = datos_formulario(paginas=["2"], doc_2=f"{finiquito},{encuesta},999999")
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos)
    estado = {d["documento"]: d["paginas"] for d in servicios.checklist_de(Paquete.query.one())}
    assert estado["Finiquito (asegurado/tercero)"] == "2" and estado["Encuesta"] == "2"


@pytest.mark.parametrize("url", ["/m/expedientes_seguros/correo-por-defecto", "/m/expedientes_seguros/aseguradoras/nueva"])
def test_formularios_de_correo_con_fichas_y_variables(entorno, entrar_como, url):
    from app.core.models import Usuario
    c = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    html = c.get(url).get_data(as_text=True)
    assert 'id="para"' in html and html.count("data-correos") == 2
    assert "correos.js" in html and "correos.css" in html
    for variable in reglas.VARIABLES:   # un botón por variable, en el asunto y en el cuerpo
        assert html.count('data-insertar="{' + variable + '}"') == 1   # una sola barra para asunto y cuerpo
        assert '"' + variable + '":' in html                # con su valor de ejemplo para la vista previa
    assert html.count("data-vista-previa ") == 1 and html.count("data-barra-datos") == 1


# ------------------------------------------------------------------- envío desde el hub

class EnviadorFalso:
    def __init__(self, falla=None):
        self.enviados, self.falla = [], falla

    def enviar(self, mensaje):
        if self.falla:
            raise self.falla
        self.enviados.append(mensaje)


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setenv("EXPEDIENTES_SMTP_SERVIDOR", "smtp.prueba")
    monkeypatch.setenv("EXPEDIENTES_SMTP_REMITENTE", "Expedientes <robot@canella.test>")
    monkeypatch.delenv("EXPEDIENTES_SMTP_USUARIO", raising=False)
    monkeypatch.delenv("EXPEDIENTES_SMTP_CONTRASENA", raising=False)
    enviador = EnviadorFalso()
    monkeypatch.setattr(servicios, "crear_enviador", lambda: enviador)
    return enviador


def test_enviar_el_paquete_desde_el_buzon_del_hub(entorno, cajero, smtp):
    servicios.guardar_modo_envio(servicios.MODO_PRODUCCION, servicios.DESTINO_PRUEBA)
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario(cc="ctoledo@canella.com.gt"))
    p = Paquete.query.one()
    assert "Enviar correo" in cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}").get_data(as_text=True)

    r = cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar", follow_redirects=True)
    assert "Correo enviado a gestrada@canella.com.gt" in r.get_data(as_text=True)
    (m,) = smtp.enviados
    assert (m["From"], m["To"], m["Cc"], m["Reply-To"]) == (
        "Expedientes <robot@canella.test>", "gestrada@canella.com.gt", "ctoledo@canella.com.gt", "cajero@canella.test")
    assert m["Subject"] == "LA CEIBA//Serie" and "X-Unsent" not in m and m["Message-ID"]
    assert [a.get_filename() for a in m.iter_attachments()] == [p.nombre_archivo]
    assert m.get_body(("plain",)).get_content().strip() == "Adjunto"
    db.session.refresh(p)
    assert p.enviado_en is not None and p.enviado_por is not None

    r = cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar", follow_redirects=True)
    assert "ya se envió" in r.get_data(as_text=True) and len(smtp.enviados) == 1   # no se duplica
    assert "Enviar correo" not in r.get_data(as_text=True)


def test_si_el_servidor_rechaza_el_correo_se_puede_reintentar(entorno, cajero, smtp):
    from app.modulos.expedientes_seguros.envio import CorreoNoEnviado
    servicios.guardar_modo_envio(servicios.MODO_PRODUCCION, servicios.DESTINO_PRUEBA)
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    p = Paquete.query.one()
    smtp.falla = CorreoNoEnviado("No se envió el correo: tiempo de espera agotado.")
    r = cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar", follow_redirects=True)
    assert "tiempo de espera agotado" in r.get_data(as_text=True)
    db.session.refresh(p)
    assert p.enviado_en is None

    smtp.falla = None
    cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar")
    assert len(smtp.enviados) == 1


def test_en_modo_prueba_solo_llega_al_destino_de_prueba(entorno, cajero, smtp):
    """Prueba es lo predeterminado: nadie de Cobros recibe nada y el paquete queda pendiente."""
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario(cc="ctoledo@canella.com.gt"))
    p = Paquete.query.one()
    html = cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}").get_data(as_text=True)
    assert "MODO PRUEBA" in html and "Enviar correo de PRUEBA" in html and "cajamauto2@canella.com.gt" in html
    assert "MODO PRUEBA" in cajero.get("/m/expedientes_seguros/").get_data(as_text=True)

    r = cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar", follow_redirects=True)
    assert "Correo de PRUEBA enviado solo a" in r.get_data(as_text=True)
    (m,) = smtp.enviados
    assert m["To"] == "cajamauto2@canella.com.gt" and m["Cc"] is None
    assert m["Subject"] == "[PRUEBA] LA CEIBA//Serie"
    cuerpo = m.get_body(("plain",)).get_content()
    assert "CORREO DE PRUEBA" in cuerpo and "Para: gestrada@canella.com.gt" in cuerpo and "CC: ctoledo@canella.com.gt" in cuerpo
    assert [a.get_filename() for a in m.iter_attachments()] == [p.nombre_archivo]
    db.session.refresh(p)
    assert p.enviado_en is None                              # se puede enviar de verdad después

    cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar")
    assert len(smtp.enviados) == 2                           # en prueba se puede repetir


def test_el_cajero_no_cambia_el_modo_de_envio(entorno, cajero):
    assert cajero.post("/m/expedientes_seguros/modo-envio", data={"modo": "produccion"}).status_code == 403
    assert servicios.modo_envio().prueba
    assert 'name="modo"' not in cajero.get("/m/expedientes_seguros/aseguradoras").get_data(as_text=True)


def test_el_administrador_cambia_el_modo_de_envio(entorno, entrar_como):
    from app.core.models import Usuario
    jefe = entrar_como(crear_usuario("jefe", rol=Usuario.ROL_ADMIN, modulos=["expedientes_seguros"]))
    html = jefe.get("/m/expedientes_seguros/aseguradoras").get_data(as_text=True)
    assert 'name="modo" value="prueba" class="form-selectgroup-input" checked' in html
    r = jefe.post("/m/expedientes_seguros/modo-envio", data={"modo": "prueba", "destino_prueba": "uno@a.com, dos@b.com"},
                  follow_redirects=True)
    assert "debe ser un solo correo válido" in r.get_data(as_text=True)
    r = jefe.post("/m/expedientes_seguros/modo-envio", data={"modo": "produccion", "destino_prueba": "yo@canella.com.gt"},
                  follow_redirects=True)
    assert "Modo PRODUCCIÓN" in r.get_data(as_text=True)
    assert servicios.modo_envio() == servicios.ModoEnvio("produccion", "yo@canella.com.gt")
    assert "MODO PRUEBA" not in jefe.get("/m/expedientes_seguros/").get_data(as_text=True)
    assert jefe.post("/m/expedientes_seguros/modo-envio", data={"modo": "otro"}).status_code == 400


def test_envio_sin_configurar_avisa_y_deja_el_eml(entorno, cajero, monkeypatch):
    monkeypatch.delenv("EXPEDIENTES_SMTP_SERVIDOR", raising=False)
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    p = Paquete.query.one()
    r = cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar", follow_redirects=True)
    assert "no está configurado" in r.get_data(as_text=True) and "EXPEDIENTES_SMTP_SERVIDOR" in r.get_data(as_text=True)
    assert Paquete.query.one().enviado_en is None
    assert cajero.get(f"/m/expedientes_seguros/paquetes/{p.id}/correo.eml").status_code == 200


def test_envio_de_paquete_vencido_avisa(entorno, cajero, smtp, monkeypatch):
    cajero.post("/m/expedientes_seguros/llamadas/51595/paquetes", data=datos_formulario())
    p = Paquete.query.one()
    monkeypatch.setattr(servicios, "adjuntos_de", lambda paquete: [])
    r = cajero.post(f"/m/expedientes_seguros/paquetes/{p.id}/enviar", follow_redirects=True)
    assert "ya se borraron" in r.get_data(as_text=True) and smtp.enviados == []


class SmtpFalso:
    """Reemplaza ``smtplib.SMTP``: registra la conversación y falla las primeras veces si se pide."""
    conexiones, fallas = [], []

    def __init__(self, servidor, puerto, timeout):
        self.pasos = [("conectar", servidor, puerto)]
        SmtpFalso.conexiones.append(self.pasos)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def ehlo(self):
        self.pasos.append("ehlo")

    def starttls(self):
        self.pasos.append("starttls")

    def login(self, usuario, contrasena):
        self.pasos.append(("login", usuario))

    def send_message(self, mensaje):
        if SmtpFalso.fallas:
            raise SmtpFalso.fallas.pop(0)
        self.pasos.append("enviar")


@pytest.fixture
def smtp_falso(monkeypatch):
    from app.modulos.expedientes_seguros import envio
    SmtpFalso.conexiones, SmtpFalso.fallas = [], []
    monkeypatch.setattr(envio.smtplib, "SMTP", SmtpFalso)
    monkeypatch.setattr(envio.time, "sleep", lambda s: None)
    return SmtpFalso


def _config_correo(**cambios):
    datos = dict(servidor="smtp.prueba", puerto=587, usuario="robot", contrasena="x", remitente="robot@canella.test",
                 tls=True, intentos=3)
    datos.update(cambios)
    return configuracion.ConfigCorreo(**datos)


def test_smtp_starttls_y_autentica_antes_de_enviar(smtp_falso):
    from app.modulos.expedientes_seguros.envio import EnviadorSmtp
    EnviadorSmtp(_config_correo()).enviar(reglas.correo_saliente("robot@canella.test", "a@b.com", "", "s", "c", []))
    assert smtp_falso.conexiones == [[("conectar", "smtp.prueba", 587), "ehlo", "starttls", "ehlo", ("login", "robot"), "enviar"]]


def test_smtp_reintenta_las_fallas_temporales_y_no_las_definitivas(smtp_falso):
    import smtplib
    from app.modulos.expedientes_seguros.envio import CorreoNoEnviado, EnviadorSmtp
    mensaje = reglas.correo_saliente("robot@canella.test", "a@b.com", "", "s", "c", [])
    smtp_falso.fallas = [smtplib.SMTPDataError(421, b"ocupado")]
    EnviadorSmtp(_config_correo()).enviar(mensaje)
    assert len(smtp_falso.conexiones) == 2 and smtp_falso.conexiones[-1][-1] == "enviar"

    smtp_falso.conexiones, smtp_falso.fallas = [], [smtplib.SMTPRecipientsRefused({"a@b.com": (550, b"no")})]
    with pytest.raises(CorreoNoEnviado, match="rechazó los destinatarios: a@b.com"):
        EnviadorSmtp(_config_correo()).enviar(mensaje)
    assert len(smtp_falso.conexiones) == 1


def test_configuracion_del_correo(monkeypatch):
    for nombre in ("SERVIDOR", "REMITENTE", "USUARIO", "CONTRASENA", "PUERTO", "TLS", "INTENTOS"):
        monkeypatch.delenv(f"EXPEDIENTES_SMTP_{nombre}", raising=False)
    with pytest.raises(configuracion.ConfiguracionIncompleta, match="EXPEDIENTES_SMTP_SERVIDOR"):
        configuracion.correo()
    monkeypatch.setenv("EXPEDIENTES_SMTP_SERVIDOR", "smtp.prueba")
    monkeypatch.setenv("EXPEDIENTES_SMTP_REMITENTE", "robot@canella.test")
    c = configuracion.correo()
    assert (c.puerto, c.tls, c.usuario, c.intentos) == (587, True, "", 3)
    monkeypatch.setenv("EXPEDIENTES_SMTP_USUARIO", "robot")
    with pytest.raises(configuracion.ConfiguracionIncompleta, match="van juntas"):
        configuracion.correo()
