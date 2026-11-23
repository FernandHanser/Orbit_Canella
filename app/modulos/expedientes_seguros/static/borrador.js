// Paquete generado: el borrador de esa llamada ya no hace falta (visor.js lo guardaba por si vencía la sesión).
(function () {
  "use strict";
  var marca = document.querySelector("[data-borrar-borrador]");
  if (!marca) return;
  var prefijo = marca.getAttribute("data-borrar-borrador");
  try {
    Object.keys(localStorage).forEach(function (clave) { if (clave.indexOf(prefijo) === 0) localStorage.removeItem(clave); });
  } catch (e) { /* modo privado */ }
})();
