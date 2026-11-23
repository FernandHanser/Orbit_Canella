/*
  Visor del expediente (Expedientes de Seguros). Sin JavaScript inline, por la CSP.
  * La casilla de cada página la marca o desmarca; Mayús + clic marca todo el rango desde la anterior.
  * Todas / Ninguna / Invertir y contador "N de total".
  * Clic en la miniatura: vista grande (ajustar al ancho / tamaño real), Anterior / Siguiente, Marcar y
    «esta página es…» para asignarla a un documento del checklist de la aseguradora.
  * Checklist en vivo: cada documento muestra en qué páginas está o si falta; antes de generar, el
    modal de confirmación del hub dice qué falta (documentos obligatorios y factura).
*/
(function () {
  "use strict";

  var rejilla = document.getElementById("rejilla-paginas");
  if (!rejilla) return;
  var casillas = Array.prototype.slice.call(rejilla.querySelectorAll("input.pagina-check"));
  var contador = document.getElementById("contador");
  var ultima = null;

  // Azul: marcada, falta decir qué documento es. Verde: marcada y con documento asignado.
  function pintar(casilla) {
    var tarjeta = casilla.closest(".pagina-expediente");
    var entrada = tarjeta.querySelector("input.pagina-doc");
    tarjeta.classList.toggle("seleccionada", casilla.checked);
    tarjeta.classList.toggle("asignada", casilla.checked && !!(entrada && entrada.value));
  }

  var entradasDoc = Array.prototype.slice.call(rejilla.querySelectorAll("input.pagina-doc"));
  var documentos = Array.prototype.slice.call(document.querySelectorAll("[data-documento]"));
  var nombres = {};
  documentos.forEach(function (d) { nombres[d.getAttribute("data-documento")] = d.getAttribute("data-nombre"); });
  var factura = document.getElementById("factura");
  var form = document.getElementById("form-paquete");
  var advertencias = document.getElementById("advertencias");

  function rangos(paginas) {
    var partes = [], i = 0;
    while (i < paginas.length) {
      var j = i;
      while (j + 1 < paginas.length && paginas[j + 1] === paginas[j] + 1) j++;
      partes.push(i === j ? String(paginas[i]) : paginas[i] + "-" + paginas[j]);
      i = j + 1;
    }
    return partes.join(", ");
  }

  // Una página puede contener varios documentos (p. ej. DPI y tarjeta de circulación en la misma
  // hoja): el campo oculto de cada página guarda sus ids separados por coma.
  function docsDe(i) {
    var valor = entradasDoc[i] ? entradasDoc[i].value : "";
    return valor ? valor.split(",") : [];
  }
  function tiene(i, id) { return docsDe(i).indexOf(id) !== -1; }
  function fijar(i, ids) { entradasDoc[i].value = ids.join(","); }

  function etiquetar(indice) {
    var etiqueta = casillas[indice].closest(".pagina-expediente").querySelector(".pagina-etiqueta");
    etiqueta.textContent = docsDe(indice).map(function (id) { return nombres[id] || ""; }).join(" · ");
    etiqueta.title = etiqueta.textContent;
    pintar(casillas[indice]);
  }

  function actualizarChecklist() {
    var conFactura = factura && factura.files && factura.files.length > 0;
    var faltan = [], cumplidos = 0, obligatorios = 0, opcionales = 0;
    documentos.forEach(function (d) {
      var id = d.getAttribute("data-documento");
      var paginas = [];
      casillas.forEach(function (c, i) { if (c.checked && tiene(i, id)) paginas.push(i + 1); });
      var esFactura = d.getAttribute("data-factura") === "1" && conFactura;
      var presente = paginas.length > 0 || esFactura;
      var obligatorio = d.getAttribute("data-obligatorio") === "1";
      var icono = d.querySelector(".checklist-icono"), estado = d.querySelector(".checklist-estado");
      icono.className = "ti checklist-icono " + (presente ? "ti-circle-check text-green" : obligatorio ? "ti-circle-x text-red" : "ti-circle text-secondary");
      estado.textContent = paginas.length ? "pág. " + rangos(paginas) : esFactura ? "PDF adjunto" : obligatorio ? "Falta" : "si aplica";
      estado.className = "checklist-estado small text-nowrap " + (presente ? "text-green" : obligatorio ? "text-red" : "text-secondary");
      if (obligatorio) { obligatorios++; if (presente) cumplidos++; else faltan.push(d.getAttribute("data-nombre")); }
      else if (presente) opcionales++;
    });
    // Avance (templates/_checklist.html): solo obligatorios; «si aplica» no mueve la barra, pero se
    // muestra aparte para que se vea que quedó incluido.
    var porcentaje = obligatorios ? Math.round(cumplidos * 100 / obligatorios) : 100;
    // Sobre: el verde sube de abajo hacia arriba según el %.
    document.querySelectorAll("[data-avance]").forEach(function (sobre) {
      sobre.setAttribute("aria-valuenow", porcentaje);
      sobre.classList.toggle("completo", porcentaje === 100);
      sobre.querySelector("[data-avance-relleno]").style.transform = "scaleY(" + porcentaje / 100 + ")";
      sobre.querySelector("[data-avance-porcentaje]").textContent = porcentaje + " %";
    });
    var faltanTexto = obligatorios - cumplidos;
    document.querySelectorAll("[data-avance-detalle]").forEach(function (t) {
      t.innerHTML = "";
      var fuerte = document.createElement("strong");
      fuerte.className = "text-body";
      fuerte.textContent = cumplidos + " de " + obligatorios;
      t.appendChild(fuerte);
      t.appendChild(document.createTextNode(faltanTexto ? " · faltan " + faltanTexto : " · completo"));
    });
    document.querySelectorAll("[data-avance-opcionales]").forEach(function (t) {
      t.textContent = opcionales ? "+" + opcionales + " si aplica" : "";
    });
    pintarChecklistModal();
    pintarPorAsignar();
    // Con todos los obligatorios cumplidos, el siguiente paso es el correo: botón para ir directo.
    var completo = obligatorios > 0 && cumplidos === obligatorios;
    document.querySelectorAll("#checklist [data-ir-correo]").forEach(function (b) { b.hidden = !completo; });
    document.querySelectorAll("[data-ayuda-checklist]").forEach(function (a) { a.hidden = completo; });
    // El modal sale solo al pasar de incompleto a completo (no al cargar ni en cada cambio).
    if (completo && estabaCompleto === false) avisarCompleto(obligatorios);
    estabaCompleto = completo;
    // Mensaje del modal de confirmación del hub (static/js/interaccion.js).
    var avisos = [];
    if (faltan.length) avisos.push("Faltan documentos obligatorios: " + faltan.join(", ") + ".");
    if (!conFactura) avisos.push("No adjuntaste el PDF de la factura: el correo dirá «Adjunto documentos y factura».");
    if (avisos.length) {
      advertencias.setAttribute("data-hay", "");
      form.setAttribute("data-confirmar", avisos.join(" ") + " ¿Generar el paquete de todos modos?");
    } else {
      advertencias.removeAttribute("data-hay");
    }
  }

  // Checklist al lado de la página ampliada: obligatorios primero con su estado, «si aplica» en gris
  // abajo; clic en uno asigna la página actual a ese documento.
  var listaModal = document.getElementById("modal-checklist");
  function pintarChecklistModal() {
    if (!listaModal) return;
    // Incluida sin documento: el mismo aviso azul que en el panel, en lugar de la ayuda.
    var avisoModal = document.getElementById("modal-por-asignar");
    if (avisoModal && typeof actual === "number" && casillas[actual]) {
      var pendiente = casillas[actual].checked && !docsDe(actual).length;
      avisoModal.hidden = !pendiente;
      document.getElementById("modal-ayuda-checklist").hidden = pendiente;
      avisoModal.querySelector("[data-por-asignar-pagina]").textContent = "Pág. " + (actual + 1) + " incluida";
    }
    var conFactura = factura && factura.files && factura.files.length > 0;
    var enPagina = typeof actual === "number" && entradasDoc[actual] ? docsDe(actual) : [];
    var html = [];
    ["1", "0"].forEach(function (grupo) {
      documentos.forEach(function (d) {
        if (d.getAttribute("data-obligatorio") !== grupo) return;
        var id = d.getAttribute("data-documento");
        var paginas = [];
        casillas.forEach(function (c, i) { if (c.checked && tiene(i, id)) paginas.push(i + 1); });
        var presente = paginas.length > 0 || (d.getAttribute("data-factura") === "1" && conFactura);
        var obligatorio = grupo === "1";
        var enEsta = enPagina.indexOf(id) !== -1;
        var icono = enEsta ? "ti-square-check text-primary" : presente ? "ti-circle-check text-green" : obligatorio ? "ti-circle-x text-red" : "ti-circle text-secondary";
        var detalle = paginas.length ? "pág. " + rangos(paginas) : presente ? "PDF adjunto" : obligatorio ? "Falta" : "si aplica";
        html.push('<button type="button" class="list-group-item list-group-item-action py-2' +
          (enEsta ? " active" : "") + (obligatorio || enEsta ? "" : " text-secondary") +
          '" data-asignar="' + id + '" aria-pressed="' + enEsta + '"' +
          ' title="' + (enEsta ? "En esta página: clic para quitarlo" : "Clic para asignarlo a esta página") + '">' +
          '<div class="d-flex align-items-center gap-2"><i class="ti ' + icono + '"></i>' +
          '<span class="flex-fill small text-start"></span><span class="small text-nowrap">' + detalle + "</span></div></button>");
      });
    });
    listaModal.innerHTML = html.join("");
    // Los nombres van como texto (no HTML) para no interpretar lo que escribió un administrador.
    var botones = listaModal.querySelectorAll("[data-asignar]");
    botones.forEach(function (b) { b.querySelector(".flex-fill").textContent = nombres[b.getAttribute("data-asignar")]; });
  }
  if (listaModal) {
    listaModal.addEventListener("click", function (evento) {
      var boton = evento.target.closest("[data-asignar]");
      if (!boton) return;
      var id = boton.getAttribute("data-asignar");
      var yaTiene = docsDe(actual);
      // Una página ya asignada no toma otro documento sin preguntar: casi siempre es un clic
      // equivocado. Solo se agrega si la misma hoja tiene los dos (p. ej. DPI y tarjeta de circulación).
      if (!tiene(actual, id) && yaTiene.length && window.hub && window.hub.confirmar) {
        var pagina = actual;
        window.hub.confirmar({
          titulo: "¿La página " + (pagina + 1) + " también es «" + nombres[id] + "»?",
          mensaje: "Esta página ya está asignada como " +
            yaTiene.map(function (d) { return "«" + nombres[d] + "»"; }).join(" y ") +
            ". Agrégalo solo si la misma hoja contiene los dos documentos. Si te equivocaste, quita primero el que tiene (clic en él).",
          boton: "Sí, también es",
          devolverFoco: listaModal,
          alConfirmar: function () { if (actual === pagina) alternar(id); },
        });
        return;
      }
      alternar(id);   // agrega o quita, sin tocar los demás de la página
    });
  }

  // Checklist del costado: con páginas marcadas sin documento, clic en un documento se los asigna.
  // Usa los mismos campos ocultos que la vista grande, así que lo hecho en un lado se ve en el otro.
  var avisoPorAsignar = document.getElementById("checklist-por-asignar");
  function porAsignar() {
    var indices = [];
    casillas.forEach(function (c, i) { if (c.checked && !docsDe(i).length) indices.push(i); });
    return indices;
  }
  function pintarPorAsignar() {
    var indices = porAsignar();
    if (avisoPorAsignar) {
      avisoPorAsignar.hidden = !indices.length;
      avisoPorAsignar.querySelector("[data-por-asignar-paginas]").textContent =
        (indices.length === 1 ? "Pág. " : "Págs. ") + rangos(indices.map(function (i) { return i + 1; }));
    }
    documentos.forEach(function (d) {
      var accionable = indices.length > 0;
      d.classList.toggle("checklist-accionable", accionable);
      if (accionable) { d.setAttribute("role", "button"); d.tabIndex = 0; }
      else { d.removeAttribute("role"); d.removeAttribute("tabindex"); }
    });
  }
  function asignarPorAsignar(id) {
    var indices = porAsignar();
    if (!indices.length) return;
    indices.forEach(function (i) { fijar(i, [id]); etiquetar(i); });
    actualizarContador();
    if (typeof guardarBorrador === "function") guardarBorrador();
  }
  documentos.forEach(function (d) {
    d.addEventListener("click", function () {
      if (d.classList.contains("checklist-accionable")) asignarPorAsignar(d.getAttribute("data-documento"));
    });
    d.addEventListener("keydown", function (evento) {
      if ((evento.key === "Enter" || evento.key === " ") && d.classList.contains("checklist-accionable")) {
        evento.preventDefault();
        asignarPorAsignar(d.getAttribute("data-documento"));
      }
    });
  });

  // Lo que se ve es lo que va en el paquete: una página quitada (casilla, Ninguna, Invertir,
  // Mayús+clic o el botón del modal) deja de tener documentos asignados.
  function normalizar() {
    casillas.forEach(function (c, i) {
      if (!c.checked && docsDe(i).length) { fijar(i, []); etiquetar(i); }
    });
  }

  function actualizarContador() {
    normalizar();
    var marcadas = casillas.filter(function (c) { return c.checked; }).length;
    contador.textContent = marcadas + " de " + casillas.length;
    document.querySelectorAll("[data-cancelar-armado]").forEach(function (b) { b.disabled = marcadas === 0; });
    contador.classList.toggle("bg-primary", marcadas > 0);
    contador.classList.toggle("text-white", marcadas > 0);
    contador.classList.toggle("bg-primary-lt", marcadas === 0);
    if (advertencias) actualizarChecklist();
  }

  casillas.forEach(function (casilla, indice) {
    pintar(casilla);
    casilla.addEventListener("click", function (evento) {
      if (evento.shiftKey && ultima !== null && ultima !== indice) {
        var desde = Math.min(ultima, indice), hasta = Math.max(ultima, indice);
        for (var i = desde; i <= hasta; i++) {
          casillas[i].checked = casilla.checked;
          pintar(casillas[i]);
        }
      }
      ultima = indice;
      pintar(casilla);
      actualizarContador();
    });
  });

  document.querySelectorAll("[data-seleccion]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      var accion = boton.getAttribute("data-seleccion");
      casillas.forEach(function (c) {
        c.checked = accion === "todas" ? true : accion === "ninguna" ? false : !c.checked;
        pintar(c);
      });
      actualizarContador();
    });
  });

  // ------------------------------------------------------------------ vista ampliada
  var modal = document.getElementById("modal-pagina");
  var Modal = window.tabler && window.tabler.Modal;
  var imagen = document.getElementById("modal-pagina-imagen");
  var titulo = document.getElementById("modal-pagina-titulo");
  var botones = Array.prototype.slice.call(rejilla.querySelectorAll("[data-ampliar]"));
  var actual = 0;

  function mostrar(indice) {
    actual = Math.max(0, Math.min(botones.length - 1, indice));
    var boton = botones[actual];
    var nueva = boton.getAttribute("data-ampliar");
    if (imagen.getAttribute("src") !== nueva) {
      // Spinner y sin la página anterior mientras llega la nueva.
      document.getElementById("modal-pagina-cargando").classList.remove("d-none");
      imagen.classList.add("invisible");
      imagen.src = nueva;
    }
    imagen.alt = "Página " + boton.getAttribute("data-pagina");
    titulo.textContent = "Página " + boton.getAttribute("data-pagina") + " de " + botones.length;
    var posicion = document.getElementById("modal-pagina-posicion");
    if (posicion) posicion.textContent = boton.getAttribute("data-pagina") + " de " + botones.length;
    modal.querySelector('[data-navegar="-1"]').disabled = actual === 0;
    modal.querySelector('[data-navegar="1"]').disabled = actual === botones.length - 1;
    pintarSello();
    pintarChecklistModal();
    if (igual) {
      var anteriores = actual > 0 ? docsDe(actual - 1) : [];
      igual.disabled = !anteriores.length;
      igual.title = anteriores.length
        ? "Asignar «" + anteriores.map(function (id) { return nombres[id]; }).join(" · ") + "» (A)"
        : "La página anterior no tiene documento asignado";
    }
  }

  var igual = document.getElementById("modal-pagina-igual");

  // Sello sobre la página ampliada: qué documento(s) es ya esta página.
  var sello = document.getElementById("modal-pagina-sello");
  function pintarSello() {
    if (!sello) return;
    var docs = casillas[actual].checked ? docsDe(actual) : [];
    sello.hidden = !docs.length;
    sello.textContent = "";
    if (!docs.length) return;
    var encabezado = document.createElement("small");
    encabezado.textContent = "✓ Asignada como";
    sello.appendChild(encabezado);
    docs.forEach(function (id) {
      var linea = document.createElement("div");
      linea.textContent = nombres[id] || "";
      sello.appendChild(linea);
    });
  }

  function asignar(ids) {
    fijar(actual, ids);
    // Decir qué documento es una página la incluye en el paquete.
    if (ids.length && !casillas[actual].checked) { casillas[actual].checked = true; pintar(casillas[actual]); }
    etiquetar(actual);
    actualizarContador();
    mostrar(actual);
    if (typeof guardarBorrador === "function") guardarBorrador();
  }
  function alternar(id) {
    var ids = docsDe(actual);
    var posicion = ids.indexOf(id);
    if (posicion === -1) ids.push(id); else ids.splice(posicion, 1);
    if (!ids.length && casillas[actual].checked) { casillas[actual].checked = false; pintar(casillas[actual]); }
    asignar(ids);
  }
  // Cancelar: la página vuelve a su estado inicial (sin documentos y fuera del paquete).
  // Cancelar ([data-cancelar-armado], en el panel del checklist y en la vista grande): descarta TODA
  // la selección (todas las páginas y sus documentos) y cierra la vista grande; se confirma con el
  // modal del hub. Por página, asignar y quitar es clic en el checklist (un clic lo pone, otro lo quita).
  var cancelar = Array.prototype.slice.call(document.querySelectorAll("[data-cancelar-armado]"));
  function cancelarTodo() {
    casillas.forEach(function (c, i) { c.checked = false; if (entradasDoc[i]) fijar(i, []); etiquetar(i); });
    actualizarContador();
    try { localStorage.removeItem(claveBorrador); } catch (e) { /* nada */ }
    if (modal && Modal) Modal.getOrCreateInstance(modal).hide();
  }
  function pedirCancelar(evento) {
    var marcadas = casillas.filter(function (c) { return c.checked; }).length;
    var conDocumento = entradasDoc.filter(function (e) { return e.value; }).length;
    if (!marcadas && !conDocumento) return;
    if (!(window.hub && window.hub.confirmar)) { cancelarTodo(); return; }
    window.hub.confirmar({
      titulo: "¿Cancelar el armado del expediente?",
      mensaje: "Se desmarcan las " + marcadas + " páginas seleccionadas" +
        (conDocumento ? " y se quitan los documentos asignados a " + conDocumento + " de ellas" : "") +
        ". El PDF original de SAP no cambia.",
      boton: "Sí, cancelar todo",
      peligro: true,
      devolverFoco: evento && evento.currentTarget,
      alConfirmar: cancelarTodo,
    });
  }
  cancelar.forEach(function (b) { b.addEventListener("click", pedirCancelar); });
  if (igual) {
    igual.addEventListener("click", function () {
      if (actual > 0 && docsDe(actual - 1).length) asignar(docsDe(actual - 1));
    });
  }
  entradasDoc.forEach(function (_, i) { etiquetar(i); });

  // Tamaño de la vista grande: ajustada al ancho (por defecto) o a tamaño real para leer detalle.
  document.querySelectorAll("[data-zoom]").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll("[data-zoom]").forEach(function (o) { o.classList.toggle("active", o === b); });
      imagen.classList.toggle("zoom-real", b.getAttribute("data-zoom") === "real");
    });
  });

  if (modal && Modal) {
    var instancia = Modal.getOrCreateInstance(modal);
    botones.forEach(function (boton, indice) {
      boton.addEventListener("click", function () { mostrar(indice); instancia.show(); });
    });
    modal.querySelectorAll("[data-navegar]").forEach(function (b) {
      b.addEventListener("click", function () { mostrar(actual + parseInt(b.getAttribute("data-navegar"), 10)); });
    });
    modal.addEventListener("keydown", function (evento) {
      if ((evento.key === "a" || evento.key === "A") && igual && !igual.disabled) igual.click();
      if (evento.key === "ArrowLeft") mostrar(actual - 1);
      if (evento.key === "ArrowRight") mostrar(actual + 1);
    });
  }

  var estabaCompleto = null;
  var modalCompleto = document.getElementById("modal-completo");
  function avisarCompleto(total) {
    if (!modalCompleto || !Modal) return;
    modalCompleto.querySelector("[data-completo-mensaje]").textContent =
      "Los " + total + " documentos obligatorios ya tienen página asignada. Sigue con el correo a Créditos y Cobros y genera el paquete.";
    Modal.getOrCreateInstance(modalCompleto).show();
  }

  // «Ir al correo»: cierra los modales abiertos (el de éxito y la vista grande) y lleva al correo.
  function irAlCorreo() {
    var correo = document.getElementById("correo");
    if (!correo) return;
    correo.scrollIntoView({ behavior: "smooth", block: "start" });
    var primero = correo.querySelector(".correos-entrada, textarea, input");
    if (primero) primero.focus({ preventScroll: true });
  }
  function cerrarYIr(pendientes) {
    var abierto = pendientes.filter(function (m) { return m && m.classList.contains("show"); })[0];
    if (!abierto || !Modal) { irAlCorreo(); return; }
    abierto.addEventListener("hidden.bs.modal", function () { cerrarYIr(pendientes); }, { once: true });
    Modal.getOrCreateInstance(abierto).hide();
  }
  document.querySelectorAll("[data-ir-correo]").forEach(function (b) {
    b.addEventListener("click", function () { cerrarYIr([modalCompleto, modal]); });
  });

  // ------------------------------------------------------------------ carga de imágenes
  // Cada miniatura muestra un spinner hasta que llega (se generan en el servidor la primera vez).
  rejilla.querySelectorAll(".pagina-expediente img").forEach(function (img) {
    var tarjeta = img.closest(".pagina-expediente");
    function listo() { tarjeta.classList.add("cargada"); }
    function fallo() { tarjeta.classList.add("cargada", "con-error"); img.alt = img.alt + " (no se pudo cargar)"; }
    if (img.complete && img.naturalWidth) listo();
    else { img.addEventListener("load", listo); img.addEventListener("error", fallo); }
  });
  if (imagen) {
    var cargando = document.getElementById("modal-pagina-cargando");
    imagen.addEventListener("load", function () { cargando.classList.add("d-none"); imagen.classList.remove("invisible"); });
    imagen.addEventListener("error", function () { cargando.classList.add("d-none"); });
  }

  // ------------------------------------------------------------------ factura
  var facturaSap = document.getElementById("factura-sap");
  if (facturaSap) {
    facturaSap.addEventListener("change", function () {
      var opcion = facturaSap.options[facturaSap.selectedIndex];
      if (!opcion.hasAttribute("data-serie")) return;
      form.elements["serie"].value = opcion.getAttribute("data-serie");
      form.elements["numero"].value = opcion.getAttribute("data-numero");
      guardarBorrador();
    });
  }
  if (factura) {
    factura.addEventListener("change", function () {
      if (factura.files && factura.files.length) factura.removeAttribute("data-vacio");
      else factura.setAttribute("data-vacio", "");
      actualizarContador();
    });
  }

  // ------------------------------------------------------------------ borrador
  // Lo marcado se guarda en el navegador mientras se trabaja; si la sesión vence, al volver a esta
  // llamada se restaura (la factura no: el navegador no permite rellenar un archivo).
  var claveBorrador = form && form.getAttribute("data-borrador");
  var CAMPOS = ["serie", "numero", "para", "cc", "asunto", "cuerpo"];
  var HORAS_BORRADOR = 12;

  var descartando = false;   // al descartar se recarga: pagehide no debe volver a guardar lo descartado

  function guardarBorrador() {
    if (!claveBorrador || descartando) return;
    var datos = { t: Date.now(), paginas: [], docs: {}, campos: {} };
    casillas.forEach(function (c, i) {
      if (c.checked) datos.paginas.push(i + 1);
      if (entradasDoc[i] && entradasDoc[i].value) datos.docs[i + 1] = entradasDoc[i].value;
    });
    CAMPOS.forEach(function (n) { var e = form.elements[n]; if (e) datos.campos[n] = e.value; });
    var separada = form.elements["factura_separada"];
    if (separada) datos.campos.factura_separada = separada.checked;
    try { localStorage.setItem(claveBorrador, JSON.stringify(datos)); } catch (e) { /* sin espacio o privado */ }
  }

  function restaurarBorrador() {
    if (!claveBorrador || form.hasAttribute("data-con-datos")) return;   // el servidor ya trae lo enviado
    var datos;
    try { datos = JSON.parse(localStorage.getItem(claveBorrador) || "null"); } catch (e) { datos = null; }
    if (!datos || Date.now() - datos.t > HORAS_BORRADOR * 3600 * 1000) return;
    if (!datos.paginas.length && !Object.keys(datos.docs).length) return;
    casillas.forEach(function (c, i) {
      var docs = datos.docs[i + 1] || "";
      c.checked = datos.paginas.indexOf(i + 1) !== -1 || docs !== "";
      pintar(c);
      if (entradasDoc[i]) { entradasDoc[i].value = docs; etiquetar(i); }
    });
    CAMPOS.forEach(function (n) { var e = form.elements[n]; if (e && n in datos.campos) e.value = datos.campos[n]; });
    var separada = form.elements["factura_separada"];
    if (separada && "factura_separada" in datos.campos) separada.checked = datos.campos.factura_separada;
    var aviso = document.getElementById("aviso-borrador");
    aviso.querySelector("[data-borrador-detalle]").textContent =
      datos.paginas.length + " páginas marcadas y el correo, guardados " + new Date(datos.t).toLocaleString("es-GT") + ".";
    aviso.classList.remove("d-none");
    function descartarBorrador() {
      descartando = true;
      try { localStorage.removeItem(claveBorrador); } catch (e) { /* nada */ }
      location.reload();   // vuelve a lo que trae el servidor: sin páginas marcadas y el correo sugerido
    }
    document.getElementById("descartar-borrador").addEventListener("click", function () {
      if (!(window.hub && window.hub.confirmar)) { descartarBorrador(); return; }
      window.hub.confirmar({
        titulo: "¿Descartar el trabajo recuperado?",
        mensaje: "Se quitan las " + datos.paginas.length + " páginas marcadas, sus documentos y los cambios al correo. Se empieza con el correo sugerido.",
        boton: "Sí, descartar",
        peligro: true,
        alConfirmar: descartarBorrador,
      });
    });
  }

  if (claveBorrador) {
    restaurarBorrador();
    form.addEventListener("change", guardarBorrador);
    form.addEventListener("input", guardarBorrador);
    document.addEventListener("sesion:vence", guardarBorrador);
    window.addEventListener("pagehide", guardarBorrador);
  }

  actualizarContador();
})();
