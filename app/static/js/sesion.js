/*
  Aviso de expiración de la sesión (núcleo). El servidor decide cuándo vence (app/core/sesion.py);
  este script solo avisa y permite extender:

  * Cuenta hacia atrás con los segundos que envía el servidor (data-sesion-* en <body>).
  * A SESION_AVISO_SEGUNDOS del final abre el modal con la cuenta regresiva:
      - por inactividad: «Extender sesión» (POST /sesion/extender) o «Cerrar sesión»;
      - por jornada: solo «Entendido» (la jornada no se extiende; hay que volver a entrar).
  * Antes de mostrarlo pregunta al servidor el tiempo real (/sesion/estado), porque otras
    pestañas o las imágenes de un visor también cuentan como actividad.
  * Pestañas sincronizadas con localStorage: extender o navegar en una reinicia el aviso en las demás.
  * Al llegar a cero lleva al login con el motivo y la página actual (?siguiente=).
  Antes de salir dispara el evento «sesion:vence» para que un módulo guarde su borrador.
*/
(function () {
  "use strict";

  var cuerpo = document.body;
  if (!cuerpo.hasAttribute("data-sesion-segundos")) return;
  var modal = document.getElementById("modal-sesion");
  var Modal = window.tabler && window.tabler.Modal;
  var CLAVE = "automate.sesion.vence";
  var aviso = parseInt(cuerpo.getAttribute("data-sesion-aviso"), 10) * 1000;
  var urlEstado = cuerpo.getAttribute("data-sesion-estado");
  var urlExtender = cuerpo.getAttribute("data-sesion-extender");
  var urlAcceso = cuerpo.getAttribute("data-sesion-acceso");
  var csrf = cuerpo.getAttribute("data-csrf");
  var vence = 0, motivo = "inactividad", consultando = false, instancia = null;

  function guardar(segundos, nuevoMotivo) {
    vence = Date.now() + segundos * 1000;
    motivo = nuevoMotivo || motivo;
    try { localStorage.setItem(CLAVE, JSON.stringify({ vence: vence, motivo: motivo })); } catch (e) { /* modo privado */ }
  }

  function formato(ms) {
    var s = Math.max(0, Math.ceil(ms / 1000));
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  function salir() {
    document.dispatchEvent(new CustomEvent("sesion:vence"));
    var destino = urlAcceso + "?motivo=" + encodeURIComponent(motivo) +
      "&siguiente=" + encodeURIComponent(location.pathname + location.search);
    location.assign(destino);
  }

  function mostrar() {
    if (!modal || !Modal) return;
    var jornada = motivo === "jornada";
    modal.querySelector("[data-sesion-texto]").textContent = jornada
      ? "Tu sesión llegó a su duración máxima. Guarda lo que estés haciendo: al terminar la cuenta tendrás que volver a entrar."
      : "Tu sesión se cerrará por inactividad, por seguridad. ¿Sigues trabajando?";
    modal.querySelector("[data-sesion-extender]").classList.toggle("d-none", jornada);
    modal.querySelector("[data-sesion-entendido]").classList.toggle("d-none", !jornada);
    instancia = instancia || Modal.getOrCreateInstance(modal, { backdrop: "static", keyboard: false });
    if (!modal.classList.contains("show")) instancia.show();
  }

  function ocultar() {
    if (instancia && modal.classList.contains("show")) instancia.hide();
  }

  function consultar() {
    consultando = true;
    return fetch(urlEstado, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { if (r.status === 401) { salir(); throw new Error("vencida"); } return r.json(); })
      .then(function (d) { guardar(d.segundos, d.motivo); })
      .catch(function () { /* sin red: se sigue con la cuenta local */ })
      .then(function () { consultando = false; });
  }

  function extender() {
    var boton = modal.querySelector("[data-sesion-extender]");
    boton.disabled = true;
    fetch(urlExtender, {
      method: "POST", credentials: "same-origin",
      headers: { "Accept": "application/json", "X-CSRFToken": csrf },
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) { guardar(d.segundos, d.motivo); ocultar(); })
      .catch(function () { salir(); })
      .then(function () { boton.disabled = false; });
  }

  function tic() {
    var falta = vence - Date.now();
    if (falta <= 0) { salir(); return; }
    if (falta <= aviso) {
      if (!consultando && !(modal && modal.classList.contains("show"))) {
        // Confirmar con el servidor antes de interrumpir: puede haber actividad en otra pestaña.
        consultar().then(function () { if (vence - Date.now() <= aviso) mostrar(); });
      }
      var cuenta = modal && modal.querySelector("[data-sesion-cuenta]");
      if (cuenta) cuenta.textContent = formato(falta);
    } else {
      ocultar();
    }
  }

  // Otra pestaña extendió o cargó una página: todas toman el nuevo vencimiento.
  window.addEventListener("storage", function (e) {
    if (e.key !== CLAVE || !e.newValue) return;
    try { var d = JSON.parse(e.newValue); vence = d.vence; motivo = d.motivo; } catch (err) { /* ignorar */ }
  });

  if (modal) {
    modal.querySelector("[data-sesion-extender]").addEventListener("click", extender);
    modal.querySelector("[data-sesion-entendido]").addEventListener("click", ocultar);
  }
  guardar(parseInt(cuerpo.getAttribute("data-sesion-segundos"), 10), cuerpo.getAttribute("data-sesion-motivo"));
  setInterval(tic, 1000);
})();
