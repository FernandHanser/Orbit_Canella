// Emblema Canella (login): un orb de puntos en 3D (thinking-orbs, servido localmente:
// static/vendor/thinking-orbs-0.3.2/) dentro del disco azul de marca (#1a2831). Variante
// "composing": una faja de varias bandas de puntos que ondula alrededor de la esfera. Se dibuja en
// canvas 2D (sin WebGL), con los puntos en el celeste del fondo del login y sombreado de
// profundidad. El logotipo CANELLA (la imagen plana del HTML) queda encima del orb.
// La esfera 3D anterior (three.js) quedó como respaldo en emblema-esfera-3d.js.
//
// Con vida, no una insignia fija:
// * el orb gira por su cuenta (lo anima la propia librería, a partir del tiempo);
// * respiración: toda la insignia crece y encoge muy despacio, y el resplandor de alrededor
//   (box-shadow) respira con ella;
// * flota hacia destinos aleatorios, como antes.
//
// Si esto no llega a correr (JavaScript desactivado, el archivo no carga, o cualquier error), la
// insignia sigue viva por su cuenta: respira y brilla por CSS puro (.emblema en automate.css),
// con el logotipo de siempre (logo_canella_blanco.png, en el HTML) sobre el disco liso.
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
  try { iniciar(contenedor, canvas); } catch (e) { /* se queda el logotipo plano y la respiración en CSS puro */ }
}

function iniciar(contenedor, canvas) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const { mode, speed, opts: base } = resolvePreset(ESTADO, 64);
  const opts = scaleRadii(scaleCounts(base, DENSIDAD), TAMANO_PUNTO);
  const geometria = MODE_FRAMES[mode];

  let lado = 120;
  function ajustarTamano() {
    lado = contenedor.clientWidth || 120;
    canvas.width = canvas.height = Math.round(lado * dpr);   // el tamaño en pantalla lo decide el CSS
  }
  ajustarTamano();
  const observador = new ResizeObserver(ajustarTamano);
  observador.observe(contenedor);

  // true: tinta clara sobre fondo oscuro (el disco azul).
  function pintar(t) {
    const interior = lado * INTERIOR;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, lado, lado);
    ctx.translate((lado - interior) / 2, (lado - interior) / 2);
    paintFrame(ctx, geometria(interior, t, opts), true, TINTE);
  }

  // "Reducir movimiento" quita el desplazamiento y el giro de los puntos (queda un cuadro fijo,
  // como hace la propia librería), no la respiración: es un detalle pequeño de marca.
  const reducirMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // La insignia flota hacia un destino aleatorio nuevo cada cierto tiempo, sin saltar (velocidad
  // independiente de los cuadros por segundo de la pantalla).
  const estado = { x: 0, y: 0 };
  const destino = { ...estado };
  const SUAVIZADO = 0.012;   // fracción del camino recorrida por cuadro a 60 fps
  let proximoCambio = 0;
  let anterior = null;
  let enPantalla = true;
  let cuadro;

  function animar(ahora) {
    try {
      const t = ahora / 1000;
      const dt = anterior === null ? 16.7 : Math.min(ahora - anterior, 100);
      anterior = ahora;

      if (!reducirMovimiento) {
        if (ahora >= proximoCambio) {
          destino.x = -12 + Math.random() * 24;
          destino.y = -13 + Math.random() * 21;
          proximoCambio = ahora + 2300 + Math.random() * 2900;
        }
        const factor = 1 - Math.pow(1 - SUAVIZADO, dt / 16.7);
        estado.x += (destino.x - estado.x) * factor;
        estado.y += (destino.y - estado.y) * factor;
      }

      // Respiración: crece y encoge despacio (ciclo de ~4.2 s), y el resplandor de alrededor
      // respira con ella (mismo valor "respiro", 0 a 1).
      const respiro = (Math.sin(t * 1.5) + 1) / 2;
      const escala = 1 + respiro * 0.09 - 0.045;
      const deriva = reducirMovimiento ? "" : `translate(${estado.x}px, ${estado.y + Math.sin(t * 1.1) * 5}px) `;
      contenedor.style.transform = `${deriva}scale(${escala.toFixed(4)})`;
      contenedor.style.boxShadow =
        `0 ${(10 + respiro * 6).toFixed(1)}px ${(24 + respiro * 12).toFixed(1)}px -8px rgba(0, 0, 0, .55), ` +
        `0 0 ${(16 + respiro * 20).toFixed(1)}px ${(2 + respiro * 5).toFixed(1)}px rgba(14, 143, 150, ${(0.22 + respiro * 0.22).toFixed(3)})`;

      pintar(reducirMovimiento ? 0.6 : t * speed);
    } catch (e) {
      // Cualquier error deja la respiración en CSS puro y el disco liso con el logotipo, no un
      // cuadro congelado.
      contenedor.style.transform = "";
      contenedor.style.boxShadow = "";
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      enPantalla = false;
      return;
    }
    if (enPantalla) cuadro = requestAnimationFrame(animar);
  }
  cuadro = requestAnimationFrame(animar);

  // Se detiene con la pestaña oculta (batería).
  document.addEventListener("visibilitychange", () => {
    enPantalla = !document.hidden;
    if (enPantalla) { anterior = null; cuadro = requestAnimationFrame(animar); }
    else cancelAnimationFrame(cuadro);
  });
  window.addEventListener("pagehide", () => {
    enPantalla = false;
    cancelAnimationFrame(cuadro);
    observador.disconnect();
  }, { once: true });
}
