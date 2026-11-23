// Parallax de la pantalla de acceso: las capas siguen al cursor a distinto ritmo.
// * El fondo (lejos) se desplaza en sentido contrario al cursor.
// * El frente (logo, título y tarjeta) se desplaza un poco a favor.
// La diferencia entre las dos da la profundidad. Usa la propiedad CSS "translate", que se
// suma al "transform: scale" de las animaciones de respiración sin reemplazarlo.
// Se desactiva si el sistema pide reducir movimiento o si no hay mouse (pantallas táctiles).
(() => {
  // Se desplaza la imagen dentro de su capa (que recorta), no la capa: así nunca se ven bordes.
  const fondo = document.querySelector("#fondoAcceso .fondo-imagen");
  const frente = document.querySelector(".fondo-acceso .container-tight");
  if (!fondo || !frente) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;

  const FONDO_PX = 24;     // desplazamiento máximo del fondo (sentido contrario al cursor)
  const FRENTE_PX = 10;    // desplazamiento máximo del frente (a favor del cursor)
  const SUAVIZADO = 0.06;  // fracción del camino recorrida por cuadro: movimiento con inercia

  const objetivo = { x: 0, y: 0 };
  const actual = { x: 0, y: 0 };
  let frame = null;

  function dibujar() {
    actual.x += (objetivo.x - actual.x) * SUAVIZADO;
    actual.y += (objetivo.y - actual.y) * SUAVIZADO;
    fondo.style.translate = `${(-actual.x * FONDO_PX).toFixed(2)}px ${(-actual.y * FONDO_PX).toFixed(2)}px`;
    frente.style.translate = `${(actual.x * FRENTE_PX).toFixed(2)}px ${(actual.y * FRENTE_PX).toFixed(2)}px`;
    const quieto = Math.abs(objetivo.x - actual.x) < 0.001 && Math.abs(objetivo.y - actual.y) < 0.001;
    frame = quieto ? null : requestAnimationFrame(dibujar);
  }

  function mover(x, y) {
    objetivo.x = x;
    objetivo.y = y;
    if (frame === null) frame = requestAnimationFrame(dibujar);
  }

  // Posición del cursor normalizada a [-1, 1] desde el centro de la ventana.
  window.addEventListener("pointermove", (e) => {
    mover((e.clientX / innerWidth) * 2 - 1, (e.clientY / innerHeight) * 2 - 1);
  }, { passive: true });
  // Al salir de la ventana, las capas vuelven al centro con la misma inercia.
  document.documentElement.addEventListener("pointerleave", () => mover(0, 0));
})();
