/*
  Editor del checklist de una aseguradora: agregar filas, subir/bajar, y ver al instante qué queda
  inactivo o marcado para quitar. El guardado y la confirmación los hace el formulario (hub).
*/
(function () {
  "use strict";
  var cuerpo = document.getElementById("filas-checklist");
  var plantilla = document.getElementById("plantilla-fila");
  if (!cuerpo || !plantilla) return;
  var nuevas = 0;

  function numerar() {
    Array.prototype.forEach.call(cuerpo.querySelectorAll("tr"), function (fila, i) {
      fila.querySelector(".numero").textContent = (i + 1) + ".";
    });
  }

  function preparar(fila) {
    fila.querySelectorAll("[data-mover]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        var hacia = parseInt(boton.getAttribute("data-mover"), 10);
        var vecina = hacia < 0 ? fila.previousElementSibling : fila.nextElementSibling;
        if (!vecina) return;
        cuerpo.insertBefore(fila, hacia < 0 ? vecina : vecina.nextElementSibling);
        numerar();
        boton.focus();
      });
    });
    var activo = fila.querySelector("[data-activo]");
    activo.addEventListener("change", function () { fila.classList.toggle("inactivo", !activo.checked); });
    var quitar = fila.querySelector("[data-quitar]");
    quitar.addEventListener("change", function () { fila.classList.toggle("por-quitar", quitar.checked); });
  }

  Array.prototype.forEach.call(cuerpo.querySelectorAll("tr"), preparar);
  document.getElementById("agregar-documento").addEventListener("click", function () {
    nuevas += 1;
    var html = plantilla.innerHTML.split("__CLAVE__").join("n" + nuevas);
    cuerpo.insertAdjacentHTML("beforeend", html);
    var fila = cuerpo.lastElementChild;
    preparar(fila);
    numerar();
    fila.querySelector("input[name^=nombre-]").focus();
  });
  numerar();
})();
