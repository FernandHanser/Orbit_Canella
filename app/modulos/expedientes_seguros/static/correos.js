// Edición amigable de correos (Expedientes de Seguros).
//
// 1. textarea[data-correos]: las direcciones se ven como fichas. Se escribe una y se confirma con Enter,
//    coma, punto y coma, espacio o al salir del campo; la ✕ la quita y Retroceso con el campo vacío quita
//    la última. Pegar una lista la separa sola. El textarea queda oculto y sigue siendo lo que se envía
//    («a; b; c»), así que el servidor valida igual que siempre.
// 2. [data-barra-datos]: una barra para asunto y cuerpo; cada botón escribe {variable} donde está el
//    cursor del último de los dos que se tocó, con un espacio antes y después si hace falta.
// 3. [data-vista-previa]: el correo completo (asunto y cuerpo) con datos de ejemplo, en vivo, sin llaves.
(function () {
  "use strict";

  var VALIDO = /^[^\s@;,<>"]+@[^\s@;,<>"]+\.[^\s@;,<>"]+$/;

  function separar(texto) {
    return texto.split(/[;,\s]+/).map(function (c) { return c.trim(); }).filter(Boolean);
  }

  function avisar(elemento) {
    elemento.dispatchEvent(new Event("input", { bubbles: true }));
    elemento.dispatchEvent(new Event("change", { bubbles: true }));
  }

  document.querySelectorAll("textarea[data-correos]").forEach(function (area) {
    var lista = separar(area.value);
    var caja = document.createElement("div");
    caja.className = "form-control correos" + (area.classList.contains("is-invalid") ? " is-invalid" : "");
    var entrada = document.createElement("input");
    entrada.type = "text";
    entrada.className = "correos-entrada";
    entrada.autocomplete = "off";
    entrada.id = area.id + "-entrada";
    entrada.placeholder = "Escribe un correo y pulsa Enter";
    var etiqueta = document.querySelector('label[for="' + area.id + '"]');
    if (etiqueta) etiqueta.htmlFor = entrada.id;

    function sincronizar() {
      area.value = lista.join("; ");
      avisar(area);
    }

    function pintar() {
      caja.querySelectorAll(".correo-ficha").forEach(function (f) { f.remove(); });
      lista.forEach(function (correo, i) {
        var valido = VALIDO.test(correo);
        var ficha = document.createElement("span");
        ficha.className = "badge correo-ficha " + (valido ? "bg-blue-lt" : "bg-red-lt");
        if (!valido) ficha.title = "Esta dirección no parece válida";
        var texto = document.createElement("span");
        texto.textContent = correo;
        var quitar = document.createElement("button");
        quitar.type = "button";
        quitar.className = "correo-quitar";
        quitar.setAttribute("aria-label", "Quitar " + correo);
        quitar.innerHTML = '<i class="ti ti-x"></i>';
        quitar.addEventListener("click", function (evento) {
          evento.stopPropagation();
          lista.splice(i, 1);
          pintar();
          sincronizar();
          entrada.focus();
        });
        ficha.appendChild(texto);
        ficha.appendChild(quitar);
        caja.insertBefore(ficha, entrada);
      });
      entrada.placeholder = lista.length ? "Agregar otro…" : "Escribe un correo y pulsa Enter";
    }

    function agregar(texto) {
      var nuevos = separar(texto).map(function (c) { return c.toLowerCase(); });
      if (!nuevos.length) return false;
      nuevos.forEach(function (c) { if (lista.indexOf(c) < 0) lista.push(c); });
      pintar();
      sincronizar();
      return true;
    }

    entrada.addEventListener("keydown", function (evento) {
      if (["Enter", ",", ";", " "].indexOf(evento.key) >= 0) {
        evento.preventDefault();
        if (agregar(entrada.value)) entrada.value = "";
      } else if (evento.key === "Backspace" && !entrada.value && lista.length) {
        lista.pop();
        pintar();
        sincronizar();
      }
    });
    entrada.addEventListener("paste", function (evento) {
      var texto = (evento.clipboardData || window.clipboardData).getData("text");
      if (/[;,\s]/.test(texto.trim())) {
        evento.preventDefault();
        agregar(entrada.value + " " + texto);
        entrada.value = "";
      }
    });
    entrada.addEventListener("blur", function () {
      if (agregar(entrada.value)) entrada.value = "";
    });
    entrada.addEventListener("focus", function () { caja.classList.add("enfocado"); });
    entrada.addEventListener("blur", function () { caja.classList.remove("enfocado"); });
    caja.addEventListener("click", function () { entrada.focus(); });

    caja.appendChild(entrada);
    area.hidden = true;
    area.insertAdjacentElement("afterend", caja);
    pintar();
  });

  // Barra de datos: inserta en el último de sus campos que se tocó (asunto o cuerpo).
  document.querySelectorAll("[data-barra-datos]").forEach(function (barra) {
    var campos = barra.getAttribute("data-destinos").split(",").map(function (id) { return document.getElementById(id); })
      .filter(Boolean);
    if (!campos.length) return;
    var destino = campos[0];
    var etiqueta = barra.querySelector("[data-destino-actual]");
    function nombre(campo) {
      var label = document.querySelector('label[for="' + campo.id + '"]');
      return label ? label.textContent.replace("*", "").trim() : campo.id;
    }
    campos.forEach(function (campo) {
      campo.addEventListener("focus", function () { destino = campo; etiqueta.textContent = nombre(campo); });
    });
    etiqueta.textContent = nombre(destino);
    barra.querySelectorAll("[data-insertar]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        var variable = boton.getAttribute("data-insertar");
        var inicio = destino.selectionStart == null ? destino.value.length : destino.selectionStart;
        var fin = destino.selectionEnd == null ? inicio : destino.selectionEnd;
        var antes = destino.value.slice(0, inicio), despues = destino.value.slice(fin);
        var texto = (antes && !/\s$/.test(antes) ? " " : "") + variable + (despues && !/^\s/.test(despues) ? " " : "");
        destino.value = antes + texto + despues;
        destino.focus();
        var cursor = antes.length + texto.length;
        destino.setSelectionRange(cursor, cursor);
        avisar(destino);
      });
    });
  });

  // Vista previa del correo completo: los datos, resaltados; el resto, tal cual (solo nodos de texto).
  document.querySelectorAll("[data-vista-previa]").forEach(function (caja) {
    var ejemplos = {}, defectos = {};
    try { ejemplos = JSON.parse(caja.getAttribute("data-ejemplos")) || {}; } catch (e) { /* sin ejemplos */ }
    try { defectos = JSON.parse(caja.getAttribute("data-defectos") || "{}") || {}; } catch (e) { /* sin defectos */ }
    // Campo vacío con valor por defecto (correo propio de una aseguradora): se muestra el de por defecto.
    function valor(campo, nombre, salida) {
      var usaDefecto = !campo.value.trim() && !!defectos[nombre];
      salida.classList.toggle("por-defecto", usaDefecto);
      salida.title = usaDefecto ? "Vacío aquí: se usa el del correo por defecto" : "";
      return usaDefecto ? defectos[nombre] : campo.value;
    }
    var pares = [["data-asunto", "[data-vista-previa-asunto]", "asunto"], ["data-cuerpo", "[data-vista-previa-cuerpo]", "cuerpo"]]
      .map(function (p) { return { campo: document.getElementById(caja.getAttribute(p[0])), salida: caja.querySelector(p[1]), nombre: p[2] }; })
      .filter(function (p) { return p.campo && p.salida; });
    function pintar(par) {
      par.salida.textContent = "";
      valor(par.campo, par.nombre, par.salida).split(/(\{[a-z]+\})/).forEach(function (parte) {
        var clave = /^\{([a-z]+)\}$/.exec(parte);
        if (clave && clave[1] in ejemplos) {
          var dato = document.createElement("mark");
          dato.className = "vista-previa-dato";
          dato.textContent = ejemplos[clave[1]];
          par.salida.appendChild(dato);
        } else if (parte) {
          par.salida.appendChild(document.createTextNode(parte));
        }
      });
    }
    pares.forEach(function (par) {
      par.campo.addEventListener("input", function () { pintar(par); });
      pintar(par);
    });
    // Destinatarios: los mismos del formulario (las fichas actualizan el campo oculto y avisan).
    [["data-para", "[data-vista-previa-para]"], ["data-cc", "[data-vista-previa-cc]"]].forEach(function (p) {
      var campo = document.getElementById(caja.getAttribute(p[0]));
      var salida = caja.querySelector(p[1]);
      if (!campo || !salida) return;
      function destinatarios() {
        var lista = valor(campo, p[0].slice(5), salida).split(/[;,\s]+/).filter(Boolean);
        salida.textContent = lista.length ? lista.join(", ") : "—";
        if (p[0] === "data-cc") caja.querySelector("[data-vista-previa-fila-cc]").hidden = !lista.length;
      }
      campo.addEventListener("input", destinatarios);
      destinatarios();
    });
  });
})();
