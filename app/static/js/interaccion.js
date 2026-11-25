/*
  Interacción común del hub (sin JavaScript inline, por la CSP). Se activa con atributos en un <form>
  (y data-cargando también en un enlace <a> que abre una página lenta):

  data-cargando="Texto…"     Al enviar: deshabilita los botones del formulario y muestra un spinner
                             con el texto. Evita dobles clics mientras el servidor trabaja.
  data-confirmar="Mensaje"   Antes de enviar: modal de confirmación. Solo para acciones con efectos
                             que no se deshacen (enviar correos, mover o borrar datos).
    data-confirmar-titulo    Título del modal (por defecto "¿Confirmas la acción?").
    data-confirmar-boton     Texto del botón que confirma (por defecto "Confirmar").
    data-confirmar-si        Selector CSS: solo se confirma si hay un elemento que coincide dentro
                             del formulario (p. ej. input[name=rol][value=admin]:checked).

  data-cargando-pagina="Mensaje…"   (en un <form> con data-cargando o en un enlace <a>): además del
                             spinner del botón, cubre la página con una pantalla de carga con el mensaje,
                             hasta que llega la siguiente. Para esperas que se sienten (consultar SAP,
                             leer un PDF). Opcionales: data-cargando-detalle="…" (segunda línea) y
                             data-cargando-logo="<url>" (p. ej. el logo de SAP).

  data-revelar-contrasena     (en un <button> junto a un campo de contraseña, con aria-controls=<id del
                             campo>): alterna entre mostrar y ocultar lo escrito. Al enviar el
                             formulario se vuelve a ocultar. Lo arma la macro campo(..., revelar=True).

  Desde JavaScript: window.hub.confirmar({titulo, mensaje, boton, peligro, devolverFoco, alConfirmar})
  abre el mismo modal.

  Modales apilados: cualquier modal que se abre con otro ya abierto (p. ej. sobre el visor de
  Expedientes) va encima con su propio fondo y, al cerrarse, el foco vuelve al de abajo.

  Ver docs/INTERFAZ.md.
*/
(function () {
  "use strict";

  function spinner(texto) {
    var fragmento = document.createDocumentFragment();
    var girando = document.createElement("span");
    girando.className = "spinner-border spinner-border-sm me-2";
    girando.setAttribute("role", "status");
    girando.setAttribute("aria-hidden", "true");
    fragmento.appendChild(girando);
    fragmento.appendChild(document.createTextNode(texto));
    return fragmento;
  }

  // Pantalla de carga: aparece con un pequeño retraso (CSS) para no parpadear si la respuesta es inmediata.
  function mostrarPantalla(origen) {
    var texto = origen.getAttribute("data-cargando-pagina");
    if (!texto || document.querySelector(".pantalla-carga")) return;
    var capa = document.createElement("div");
    capa.className = "pantalla-carga";
    capa.setAttribute("role", "status");
    capa.setAttribute("aria-live", "polite");
    var caja = document.createElement("div");
    caja.className = "pantalla-carga-caja";
    var logo = origen.getAttribute("data-cargando-logo");
    if (logo) {
      var imagen = document.createElement("img");
      imagen.src = logo;
      imagen.alt = "";
      imagen.className = "pantalla-carga-logo";
      caja.appendChild(imagen);
    }
    var girando = document.createElement("div");
    girando.className = "spinner-border text-primary";
    girando.setAttribute("aria-hidden", "true");
    caja.appendChild(girando);
    var titulo = document.createElement("div");
    titulo.className = "pantalla-carga-texto";
    titulo.textContent = texto;
    caja.appendChild(titulo);
    var detalle = origen.getAttribute("data-cargando-detalle");
    if (detalle) {
      var linea = document.createElement("div");
      linea.className = "pantalla-carga-detalle";
      linea.textContent = detalle;
      caja.appendChild(linea);
    }
    capa.appendChild(caja);
    document.body.appendChild(capa);
  }
  window.hub = window.hub || {};
  window.hub.pantallaCarga = mostrarPantalla;

  // Enlaces que abren una página lenta (consultan un sistema externo): spinner y sin dobles clics.
  document.addEventListener("click", function (evento) {
    var enlace = evento.target.closest && evento.target.closest("a[data-cargando]");
    if (!enlace || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0) return;
    if (enlace.getAttribute("aria-busy") === "true") { evento.preventDefault(); return; }
    enlace.setAttribute("aria-busy", "true");
    enlace.classList.add("disabled");
    enlace.textContent = "";
    enlace.appendChild(spinner(enlace.getAttribute("data-cargando")));
    mostrarPantalla(enlace);
  });

  // Mostrar u ocultar la contraseña (botón con el ojo).
  function revelarContrasena(boton, mostrar) {
    var campo = document.getElementById(boton.getAttribute("aria-controls"));
    if (!campo) return;
    campo.type = mostrar ? "text" : "password";
    var texto = mostrar ? "Ocultar contraseña" : "Mostrar contraseña";
    boton.setAttribute("aria-pressed", mostrar ? "true" : "false");
    boton.setAttribute("aria-label", texto);
    boton.title = texto;
    var icono = boton.querySelector(".ti");
    if (icono) icono.className = "ti " + (mostrar ? "ti-eye-off" : "ti-eye");
  }

  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-revelar-contrasena]");
    if (!boton) return;
    revelarContrasena(boton, boton.getAttribute("aria-pressed") !== "true");
  });

  function mostrarCargando(form) {
    var texto = form.getAttribute("data-cargando");
    form.setAttribute("aria-busy", "true");
    form.querySelectorAll("button, input[type=submit]").forEach(function (boton) {
      boton.disabled = true;
      if (boton.type === "submit" && boton.tagName === "BUTTON") {
        boton.textContent = "";
        boton.appendChild(spinner(texto));
      }
    });
    mostrarPantalla(form);
  }

  function confirmar(opciones) {
    var modal = document.getElementById("modal-confirmar");
    var Modal = window.tabler && window.tabler.Modal;
    if (!modal || !Modal) {
      if (window.confirm(opciones.mensaje)) opciones.alConfirmar();
      return;
    }
    modal.querySelector("[data-modal-titulo]").textContent = opciones.titulo || "¿Confirmas la acción?";
    modal.querySelector("[data-modal-mensaje]").textContent = opciones.mensaje || "";
    var aceptar = modal.querySelector("[data-modal-aceptar]");
    aceptar.textContent = opciones.boton || "Confirmar";
    // Amarillo = advertencia; rojo = la acción descarta trabajo.
    var color = opciones.peligro ? "danger" : "warning";
    aceptar.className = "btn btn-" + color + " w-100";
    modal.querySelector(".modal-status").className = "modal-status bg-" + color;
    modal.querySelector("[data-modal-icono]").className = "ti ti-alert-triangle mb-2 modal-confirmar-icono text-" + color;

    var instancia = Modal.getOrCreateInstance(modal);
    // Foco en "Cancelar": un Enter accidental no ejecuta la acción.
    modal.addEventListener("shown.bs.modal", function () {
      var cancelar = modal.querySelector("[data-bs-dismiss=modal].btn");
      if (cancelar) cancelar.focus();
    }, { once: true });
    if (opciones.devolverFoco) {
      modal.addEventListener("hidden.bs.modal", function () {
        if (document.querySelector(".modal.show")) opciones.devolverFoco.focus();
      }, { once: true });
    }
    aceptar.onclick = function () {
      instancia.hide();
      opciones.alConfirmar();
    };
    instancia.show();
  }
  window.hub = window.hub || {};
  window.hub.confirmar = confirmar;

  // Modal sobre modal: z-index mayor (.modal-apilado en automate.css; el segundo fondo también sube).
  document.addEventListener("show.bs.modal", function (evento) {
    var debajo = document.querySelector(".modal.show");
    if (!debajo || debajo === evento.target) return;
    evento.target.classList.add("modal-apilado");
    evento.target._modalDebajo = debajo;
  });
  document.addEventListener("hidden.bs.modal", function (evento) {
    var debajo = evento.target._modalDebajo;
    if (!debajo) return;
    evento.target.classList.remove("modal-apilado");
    evento.target._modalDebajo = null;
    if (debajo.classList.contains("show")) {
      document.body.classList.add("modal-open");   // Bootstrap la quita al cerrar el de arriba
      if (!debajo.contains(document.activeElement)) debajo.focus();
    }
  });

  function pedirConfirmacion(form, alConfirmar) {
    confirmar({
      titulo: form.getAttribute("data-confirmar-titulo"),
      mensaje: form.getAttribute("data-confirmar"),
      boton: form.getAttribute("data-confirmar-boton"),
      alConfirmar: alConfirmar,
    });
  }

  document.addEventListener("submit", function (evento) {
    var form = evento.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.getAttribute("aria-busy") === "true") {
      evento.preventDefault(); // ya se envió: ignora clics repetidos
      return;
    }
    // La contraseña nunca viaja ni queda en pantalla como texto visible.
    form.querySelectorAll("[data-revelar-contrasena]").forEach(function (boton) { revelarContrasena(boton, false); });
    var condicion = form.getAttribute("data-confirmar-si");
    var requiereConfirmar = form.hasAttribute("data-confirmar") && (!condicion || form.querySelector(condicion));
    if (requiereConfirmar && !form.dataset.confirmado) {
      evento.preventDefault();
      pedirConfirmacion(form, function () {
        form.dataset.confirmado = "1";
        if (form.hasAttribute("data-cargando")) mostrarCargando(form);
        form.submit(); // submit() no vuelve a disparar este evento
      });
      return;
    }
    if (form.hasAttribute("data-cargando")) mostrarCargando(form);
  });

  // Al volver con el botón "Atrás", el navegador puede restaurar la página con los botones bloqueados.
  window.addEventListener("pageshow", function (evento) {
    if (evento.persisted && document.querySelector("[aria-busy=true], .pantalla-carga")) window.location.reload();
  });
})();
