"""Pantallas: buscar la llamada, visor de páginas, generar el paquete, descargarlo y enviarlo.

Sin decoradores de seguridad: el núcleo exige sesión y el permiso del módulo en todas las rutas
(incluidas las imágenes de las páginas, que contienen datos personales; CA-08).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from datetime import time as dt_time
from urllib.parse import quote

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.core.logs import get_logger
from app.core.paginacion import POR_PAGINA, PaginaLista, pagina_actual
from app.core.permisos import es_administrador
from app.extensions import db

from . import configuracion, documentos, reglas, servicios
from .envio import CorreoNoEnviado
from .models import Paquete
from .sap import SapNoDisponible

bp = Blueprint("expedientes_seguros", __name__, template_folder="templates",
               static_folder="static", static_url_path="/static")
log = get_logger("expedientes_seguros")

MAX_FACTURA_BYTES = 20 * 1024 * 1024
ANCHOS = {"miniatura": documentos.ANCHO_MINIATURA, "ampliada": documentos.ANCHO_AMPLIADA}


@bp.context_processor
def _modo_envio():
    # Función, no valor: solo consulta la base en las pantallas que muestran el aviso.
    return {"modo_envio": servicios.modo_envio}


def _entero(valor) -> int | None:
    return int(valor) if str(valor or "").strip().isdigit() else None


@bp.route("/")
def inicio():
    ceco = request.args.get("ceco") or configuracion.ceco_por_defecto()
    aseguradora = request.args.get("aseguradora") or ""
    filas, aviso_bandeja, falta_config = [], None, None
    try:
        filas = servicios.bandeja(ceco)
    except configuracion.ConfiguracionIncompleta as exc:
        falta_config = str(exc)
    except SapNoDisponible as exc:
        log.error("Bandeja no disponible: %s", exc, extra={"evento": "expedientes.bandeja_no_disponible"})
        aviso_bandeja = "No se pudo consultar SAP para la bandeja. Puedes abrir una llamada con el buscador."
    aseguradoras = sorted({(f.pendiente.aseguradora_codigo, f.pendiente.aseguradora_nombre) for f in filas}, key=lambda a: a[1])
    visibles = [f for f in filas if not aseguradora or f.pendiente.aseguradora_codigo == aseguradora]
    bandeja = PaginaLista(visibles, pagina_actual(), POR_PAGINA)
    hoy = Paquete.query.filter(Paquete.creado_en >= _inicio_de_hoy_utc()).order_by(Paquete.creado_en.desc()).all()
    return render_template(
        "expedientes_seguros/inicio.html", bandeja=bandeja, total_pendientes=len(filas), aseguradoras=aseguradoras,
        aseguradora=aseguradora, aviso_bandeja=aviso_bandeja, paquetes_hoy=hoy, ceco=ceco,
        llamada=request.args.get("llamada", ""), falta_config=falta_config, puede_configurar=es_administrador(),
        # El buscador revisa primero aquí (en el navegador) antes de ir a SAP.
        pendientes=[{"llamada": f.pendiente.call_id, "cliente": f.pendiente.aseguradora_nombre, "dias": f.dias,
                     "url": url_for("expedientes_seguros.visor", call_id=f.pendiente.call_id, ceco=ceco)} for f in filas],
    )


@bp.route("/paquetes")
def paquetes():
    pagina = Paquete.query.order_by(Paquete.creado_en.desc(), Paquete.id.desc()).paginate(
        page=pagina_actual(), per_page=POR_PAGINA, error_out=False)
    return render_template("expedientes_seguros/paquetes.html", paquetes=pagina.items, pagina=pagina)


def _inicio_de_hoy_utc() -> datetime:
    return datetime.combine(date.today(), dt_time.min).astimezone().astimezone(timezone.utc).replace(tzinfo=None)


@bp.route("/buscar")
def buscar():
    call_id = _entero(request.args.get("llamada"))
    ceco = (request.args.get("ceco") or "").strip()
    if call_id is None:
        flash("Escribe el número de la llamada de servicio (solo números).", "warning")
        return redirect(url_for("expedientes_seguros.inicio", ceco=ceco))
    return redirect(url_for("expedientes_seguros.visor", call_id=call_id, ceco=ceco))


def _cargar(call_id: int, ceco: str):
    """(llamada, secciones del expediente combinado, total de páginas) o una redirección con el motivo."""
    volver = redirect(url_for("expedientes_seguros.inicio", llamada=call_id, ceco=ceco))
    try:
        llamada, motivo = servicios.buscar(call_id, ceco)
        if llamada is None:
            flash(motivo, "warning")
            return None, volver
        bloques = servicios.bloques_de(llamada)
        secciones, mapa = servicios.paginas_combinadas(bloques)
        total = len(mapa)
    except configuracion.ConfiguracionIncompleta as exc:
        flash(f"El módulo no está configurado: {exc}", "danger")
        return None, volver
    except SapNoDisponible as exc:
        log.error("SAP no disponible: %s", exc, extra={"evento": "expedientes.sap_no_disponible"})
        flash("No se pudo consultar SAP. Intenta en unos minutos; si continúa, avisa a Informática.", "danger")
        return None, volver
    except FileNotFoundError as exc:
        log.error("%s", exc, extra={"evento": "expedientes.anexo_no_encontrado"})
        flash("SAP indica un expediente, pero no se pudo abrir en el servidor de archivos. Avisa a Informática.", "danger")
        return None, volver
    except documentos.PdfInvalido:
        flash("El anexo de la llamada no es un PDF válido.", "danger")
        return None, volver
    return (llamada, secciones, total), None


@bp.route("/llamadas/<int:call_id>")
def visor(call_id: int):
    ceco = (request.args.get("ceco") or "").strip()
    cargado, respuesta = _cargar(call_id, ceco)
    if respuesta:
        return respuesta
    llamada, secciones, total = cargado
    sugerido = servicios.correo_sugerido(llamada)
    return render_template(
        "expedientes_seguros/visor.html", llamada=llamada, secciones=secciones, total=total, ceco=ceco,
        correo=sugerido, seleccion=set(), errores=[], abierto_en=int(time.time()),
        documentos=servicios.checklist(servicios.aseguradora_de(llamada.aseguradora_codigo)), asignaciones={},
        nombre_sugerido=reglas.nombre_paquete(llamada.call_id, llamada.aseguradora_nombre, date.today()),
    )


@bp.route("/llamadas/<int:call_id>/anexos/<int:linea>/paginas/<int:pagina>.jpg")
def imagen_pagina(call_id: int, linea: int, pagina: int):
    ancho = ANCHOS.get(request.args.get("tamano"), documentos.ANCHO_MINIATURA)
    try:
        ruta = servicios.ruta_anexo(call_id, linea)
        if ruta is None:
            abort(404)
        return Response(servicios.imagen(ruta, pagina, ancho), mimetype="image/jpeg")
    except IndexError:
        abort(404)
    except (SapNoDisponible, FileNotFoundError, configuracion.ConfiguracionIncompleta):
        abort(503)


@bp.route("/llamadas/<int:call_id>/paquetes", methods=["POST"])
def generar(call_id: int):
    ceco = (request.form.get("ceco") or "").strip()
    cargado, respuesta = _cargar(call_id, ceco)
    if respuesta:
        return respuesta
    llamada, secciones, total = cargado
    f = request.form
    paginas = reglas.paginas_elegidas(f.getlist("paginas"), total)
    correo = {k: (f.get(k) or "").strip() for k in ("para", "cc", "asunto", "cuerpo", "serie", "numero")}
    correo["factura_separada"] = f.get("factura_separada") == "1"
    aseguradora = servicios.aseguradora_de(llamada.aseguradora_codigo)
    correo["aseguradora_configurada"] = aseguradora is not None
    checklist = servicios.checklist(aseguradora)
    validos = {d["id"] for d in checklist}
    asignaciones = {}
    for n in range(1, total + 1):
        # Una página puede tener varios documentos: "3,7". Se ignoran ids ajenos a la aseguradora.
        ids = [int(v) for v in (f.get(f"doc_{n}") or "").split(",") if v.strip().isdigit() and int(v) in validos]
        if ids:
            asignaciones[n] = sorted(set(ids))

    errores = []
    if not paginas:
        errores.append("Selecciona al menos una página del expediente.")
    if not correo["serie"] or not correo["numero"]:
        errores.append("Falta la Serie o el Número de la factura: complétalos antes de generar.")
    if not reglas.direcciones(correo["para"]):
        errores.append("Indica al menos un destinatario en «Para».")
    for campo in ("para", "cc"):
        invalido = reglas.correo_invalido(correo[campo])
        if invalido:
            errores.append(f"La dirección «{invalido}» no es válida.")
    if not correo["asunto"]:
        errores.append("El asunto está vacío.")

    factura = None
    archivo = request.files.get("factura")
    if archivo and archivo.filename:
        factura = archivo.read(MAX_FACTURA_BYTES + 1)
        if len(factura) > MAX_FACTURA_BYTES:
            errores.append("La factura supera 20 MB.")
        else:
            try:
                documentos.contar_paginas(factura)
            except documentos.PdfInvalido:
                errores.append("La factura adjunta no es un PDF válido.")

    if errores:
        return render_template(
            "expedientes_seguros/visor.html", llamada=llamada, secciones=secciones, total=total, ceco=ceco,
            correo=correo, seleccion=set(paginas), errores=errores, abierto_en=_entero(f.get("abierto_en")) or int(time.time()),
            documentos=checklist, asignaciones=asignaciones,
            nombre_sugerido=reglas.nombre_paquete(llamada.call_id, llamada.aseguradora_nombre, date.today()),
        ), 422

    documentos_aparte = {d["id"]: d["nombre"] for d in checklist if d["separado"]}
    paquete = servicios.armar_paquete(llamada, servicios.Solicitud(
        paginas=paginas, serie=correo["serie"], numero=correo["numero"], para=correo["para"], cc=correo["cc"],
        asunto=correo["asunto"], cuerpo=correo["cuerpo"], factura=factura, factura_separada=correo["factura_separada"],
        abierto_en=_entero(f.get("abierto_en")), asignaciones=asignaciones, documentos_aparte=documentos_aparte,
        checklist=reglas.evaluar_checklist(checklist, asignaciones, paginas, factura is not None) if checklist else None,
    ), usuario_id=current_user.id)
    flash(f"Paquete {paquete.nombre_archivo} generado con {paquete.cantidad_paginas} páginas.", "success")
    return redirect(url_for("expedientes_seguros.paquete", paquete_id=paquete.id))


@bp.route("/paquetes/<int:paquete_id>")
def paquete(paquete_id: int):
    fila = db.session.get(Paquete, paquete_id) or abort(404)
    archivos = servicios.adjuntos_de(fila)
    return render_template("expedientes_seguros/paquete.html", paquete=fila, archivos=archivos,
                           checklist=servicios.checklist_de(fila),
                           vencido=not archivos, retencion=configuracion.retencion_dias())


@bp.route("/paquetes/<int:paquete_id>/archivos/<path:nombre>")
def descargar(paquete_id: int, nombre: str):
    fila = db.session.get(Paquete, paquete_id) or abort(404)
    for adjunto in servicios.adjuntos_de(fila):
        if adjunto.nombre == nombre:
            log.info("Paquete descargado", extra={"evento": "expedientes.descarga", "datos": {"paquete": fila.id, "archivo": nombre}})
            return Response(adjunto.contenido, mimetype="application/pdf",
                            headers={"Content-Disposition": _disposicion(nombre)})
    abort(404)


@bp.route("/paquetes/<int:paquete_id>/correo.eml")
def correo(paquete_id: int):
    fila = db.session.get(Paquete, paquete_id) or abort(404)
    contenido = servicios.eml(fila)
    if contenido is None:
        abort(404)
    log.info("Correo preparado", extra={"evento": "expedientes.correo", "datos": {"paquete": fila.id}})
    return Response(contenido, mimetype="message/rfc822",
                    headers={"Content-Disposition": _disposicion(f"{fila.nombre_archivo[:-4]}.eml")})


@bp.route("/paquetes/<int:paquete_id>/enviar", methods=["POST"])
def enviar(paquete_id: int):
    fila = db.session.get(Paquete, paquete_id) or abort(404)
    volver = redirect(url_for("expedientes_seguros.paquete", paquete_id=fila.id))
    try:
        destino_prueba = servicios.enviar(fila, current_user.id, responder_a=current_user.email)
    except configuracion.ConfiguracionIncompleta as exc:
        flash(f"El envío de correo no está configurado: {exc}. Puedes abrirlo en Outlook mientras tanto.", "danger")
        return volver
    except CorreoNoEnviado as exc:
        log.error("%s", exc, extra={"evento": "expedientes.correo_no_enviado", "datos": {"paquete": fila.id}})
        flash(f"{exc} Puedes reintentar o abrirlo en Outlook.", "danger")
        return volver
    if destino_prueba:
        flash(f"Correo de PRUEBA enviado solo a {destino_prueba} (no a Cobros). "
              "El paquete sigue pendiente de enviar en producción.", "warning")
    else:
        flash(f"Correo enviado a {fila.para}.", "success")
    return volver


def _disposicion(nombre: str) -> str:
    ascii_ = nombre.encode("ascii", "ignore").decode().replace('"', "")
    return f'attachment; filename="{ascii_}"; filename*=UTF-8\'\'{quote(nombre)}'
