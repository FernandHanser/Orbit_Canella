/*
  Menú lateral que se oculta (pantallas grandes; en celular ya se pliega con el botón de Tabler).

  Se carga en <head> sin defer, a propósito: pone la clase «menu-oculto» en <html> antes de pintar
  la página, así el menú no aparece y desaparece en cada navegación. La preferencia es de cada
  navegador (localStorage), no del usuario en el servidor: es una comodidad de pantalla.

  Botones: [data-menu-ocultar] y [data-menu-mostrar]. Atajo: Ctrl + B (como en los editores).
  Ver docs/INTERFAZ.md.
*/
(function () {
  "use strict";

  var CLAVE = "orbit.menu";
  var raiz = document.documentElement;

  function leer() {
    try { return localStorage.getItem(CLAVE) === "oculto"; } catch (e) { return false; }
  }

  function aplicar(oculto, guardar) {
    raiz.classList.toggle("menu-oculto", oculto);
    if (guardar) {
      try { localStorage.setItem(CLAVE, oculto ? "oculto" : "visible"); } catch (e) { /* modo privado */ }
    }
    document.querySelectorAll("[data-menu-ocultar], [data-menu-mostrar]").forEach(function (b) {
      b.setAttribute("aria-expanded", oculto ? "false" : "true");
    });
  }

  aplicar(leer(), false);

  function alternar(enfocar) {
    var oculto = !raiz.classList.contains("menu-oculto");
    aplicar(oculto, true);
    // El foco pasa al botón que queda visible: quien usa teclado no lo pierde.
    var destino = document.querySelector(oculto ? "[data-menu-mostrar]" : "[data-menu-ocultar]");
    if (enfocar && destino) { destino.focus(); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    aplicar(raiz.classList.contains("menu-oculto"), false);
    document.addEventListener("click", function (ev) {
      if (ev.target.closest("[data-menu-ocultar], [data-menu-mostrar]")) { alternar(true); }
    });
    document.addEventListener("keydown", function (ev) {
      if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && !ev.shiftKey && (ev.key === "b" || ev.key === "B")) {
        ev.preventDefault();
        alternar(false);
      }
    });
  });

  // Otra pestaña cambió la preferencia: se sigue igual aquí.
  window.addEventListener("storage", function (ev) {
    if (ev.key === CLAVE) { aplicar(ev.newValue === "oculto", false); }
  });
})();
