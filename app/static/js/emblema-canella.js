// Emblema Canella (login): un orb de puntos en 3D (thinking-orbs, servido localmente:
// static/vendor/thinking-orbs-0.3.2/) dentro del disco azul de marca (#1a2831). Variante
// "composing": una faja de varias bandas de puntos que ondula alrededor de la esfera. Se dibuja en
// canvas 2D (sin WebGL), con los puntos en el celeste del fondo del login y sombreado de
// profundidad. El logotipo CANELLA (la imagen plana del HTML) queda encima del orb.
// La esfera 3D anterior (three.js) quedó como respaldo en emblema-esfera-3d.js.
//
// El disco está quieto (sin flotar, respirar ni sombra): lo único vivo son las partículas, que
// anima la propia librería a partir del tiempo. Si esto no corre, queda el disco con el logotipo.
import { MODE_FRAMES, resolvePreset, paintFrame } from "../vendor/thinking-orbs-0.3.2/engine.es.js";
// scaleCounts no se reexporta en "engine": se toma del mismo módulo interno (versión fijada).
import { s as scaleCounts, a as scaleRadii } from "../vendor/thinking-orbs-0.3.2/index-B8WsUNf5.js";

const ESTADO = "composing";
const TINTE = { r: 0xa4, g: 0xd1, b: 0xe4 };   // celeste del fondo (#a4d1e4); undefined: blanco de la librería
// Los ajustes de la librería están pensados para 64 px; a 120 px los puntos se ven ralos.
const DENSIDAD = 1.4;
const TAMANO_PUNTO = 1;
const INTERIOR = 0.82;   // fracción del disco que ocupa el orb: que no toque el borde

const contenedor = document.getElementById("emblemaCanella");
const canvas = contenedor && contenedor.querySelector(".emblema-esfera");
if (contenedor && canvas) {
  try { iniciar(contenedor, canvas); } catch (e) { /* se queda el disco con el logotipo */ }
}

function iniciar(contenedor, canvas) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const { mode, speed, opts: base } = resolvePreset(ESTADO, 64);
  const opts = scaleRadii(scaleCounts(base, DENSIDAD), TAMANO_PUNTO);
  const geometria = MODE_FRAMES[mode];

  // "Reducir movimiento" deja las partículas en un cuadro fijo, como hace la propia librería.
  const reducirMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let lado = 120;
  function ajustarTamano() {
    lado = contenedor.clientWidth || 120;
    canvas.width = canvas.height = Math.round(lado * dpr);   // el tamaño en pantalla lo decide el CSS
  }
  ajustarTamano();
  // Cambiar el tamaño del canvas lo borra: con el cuadro fijo hay que volver a pintarlo.
  const observador = new ResizeObserver(() => { ajustarTamano(); if (reducirMovimiento) pintar(0.6); });
  observador.observe(contenedor);

  // true: tinta clara (pensada para fondo oscuro); los puntos llevan el TINTE celeste.
  function pintar(t) {
    const interior = lado * INTERIOR;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, lado, lado);
    ctx.translate((lado - interior) / 2, (lado - interior) / 2);
    paintFrame(ctx, geometria(interior, t, opts), true, TINTE);
  }

  let enPantalla = true;
  let cuadro;

  function animar(ahora) {
    try {
      pintar(ahora / 1000 * speed);
    } catch (e) {
      // Cualquier error deja el disco liso con el logotipo, no un cuadro congelado.
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      enPantalla = false;
      return;
    }
    if (enPantalla) cuadro = requestAnimationFrame(animar);
  }
  if (reducirMovimiento) pintar(0.6);
  else cuadro = requestAnimationFrame(animar);

  // Se detiene con la pestaña oculta (batería).
  document.addEventListener("visibilitychange", () => {
    enPantalla = !document.hidden;
    if (enPantalla && !reducirMovimiento) cuadro = requestAnimationFrame(animar);
    else cancelAnimationFrame(cuadro);
  });
  window.addEventListener("pagehide", () => {
    enPantalla = false;
    cancelAnimationFrame(cuadro);
    observador.disconnect();
  }, { once: true });
}
