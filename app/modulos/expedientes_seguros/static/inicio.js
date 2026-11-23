// Inicio de Expedientes de Seguros.
// * El filtro por cliente se aplica al elegirlo (sin botón).
// * Buscador: mientras se escribe, revisa primero las pendientes (ya cargadas en la página); si está,
//   ofrece abrirla directo. Al buscar, la pantalla de carga dice qué llamada se busca en SAP.
(function () {
  "use strict";
  document.querySelectorAll("select[data-enviar-al-cambiar]").forEach(function (lista) {
    lista.addEventListener("change", function () { lista.form.submit(); });
  });

  var form = document.querySelector("form.buscador-llamada");
  if (!form) return;
  var entrada = form.querySelector("#llamada");
  var pista = document.getElementById("pista-llamada");
  var pendientes = {};
  try {
    JSON.parse(form.getAttribute("data-pendientes") || "[]").forEach(function (p) { pendientes[String(p.llamada)] = p; });
  } catch (e) { /* sin pendientes */ }

  function antiguedad(dias) { return dias === 0 ? "hoy" : dias === 1 ? "ayer" : "hace " + dias + " días"; }

  function revisar() {
    var numero = entrada.value.replace(/\D/g, "");
    pista.textContent = "";
    if (!numero) {   // sin número, sin pista
      form.setAttribute("data-cargando-pagina", "Buscando la llamada en SAP…");
      return;
    }
    var p = pendientes[numero];
    if (p) {
      var ok = document.createElement("span");
      ok.className = "text-green fw-bold";
      ok.innerHTML = '<i class="ti ti-circle-check me-1"></i>';
      ok.appendChild(document.createTextNode("Está en tus pendientes"));
      var datos = document.createElement("span");
      datos.className = "text-secondary ms-1";
      datos.textContent = "· " + p.cliente + " · abierta " + antiguedad(p.dias) + " ·";
      var abrir = document.createElement("a");
      abrir.href = p.url;
      abrir.className = "ms-1 fw-bold";
      abrir.textContent = "Armar →";
      abrir.setAttribute("data-cargando", "Abriendo…");
      abrir.setAttribute("data-cargando-pagina", "Abriendo la llamada " + numero + "…");
      abrir.setAttribute("data-cargando-detalle", form.getAttribute("data-cargando-detalle"));
      abrir.setAttribute("data-cargando-logo", form.getAttribute("data-cargando-logo"));
      pista.appendChild(ok);
      pista.appendChild(datos);
      pista.appendChild(abrir);
      form.setAttribute("data-cargando-pagina", "Abriendo la llamada " + numero + "…");
    } else {
      var sap = document.createElement("span");
      sap.className = "text-secondary";
      sap.innerHTML = '<i class="ti ti-cloud-search me-1"></i>';
      sap.appendChild(document.createTextNode("No está en tus pendientes · se buscará en SAP"));
      pista.appendChild(sap);
      form.setAttribute("data-cargando-pagina", "Buscando la llamada " + numero + " en SAP…");
    }
  }
  entrada.addEventListener("input", revisar);
  revisar();
})();
