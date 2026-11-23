// RESPALDO, NO SE CARGA EN NINGUNA PÁGINA: es el emblema anterior del login, reemplazado por el orb
// de puntos de emblema-canella.js. Para volver a él, cambiar el <script> de base_publica.html a
// este archivo (three.js sigue en static/vendor/three-0.180.0/); el HTML y el CSS le sirven igual.
//
// Emblema Canella (login): una esfera 3D real (three.js, servido localmente: static/vendor/) con
// el color de marca (#1a2831). El logotipo "CANELLA" está impreso sobre la propia curva de la
// esfera (una textura en una porción de esfera, no una imagen plana encima): recibe las mismas
// luces que el resto —el brillo pasa por encima igual— y no es una capa aparte pegada en 2D.
// Esa placa con el logotipo no gira con la esfera (si girara, el texto desaparecería de vista al
// dar la vuelta): se queda siempre de frente, como el escudo fijo de una medalla que gira debajo.
//
// Con vida, no una insignia fija:
// * brillo que recorre la superficie por su cuenta (una luz que orbita, no el giro de la esfera);
// * la esfera gira a tramos: cada uno va de una velocidad a otra (de casi quieta a un arrebato
//   rápido) con una curva de aceleración y frenado, nunca a saltos; a veces cambia de sentido.
//   Además "mira" para los lados, con inclinaciones propias en los otros dos ejes;
// * respiración: toda la insignia crece y encoge muy despacio, y el resplandor de alrededor
//   (box-shadow) respira con ella;
// * flota hacia destinos aleatorios, como antes.
//
// Si esto no llega a correr (JavaScript desactivado, el archivo no carga, o cualquier error), o
// si no hay WebGL, la insignia sigue viva por su cuenta: respira y brilla por CSS puro
// (.emblema en automate.css), con el logotipo plano de siempre (logo_canella_blanco.png, en el
// HTML). Ese logotipo plano se oculta solo cuando el de la esfera ya está listo para mostrarse.
import * as THREE from "../vendor/three-0.180.0/build/three.module.min.js";

const AZUL_MARCA = 0x1a2831;   // el mismo de .resto-nombre y del logotipo (ver automate.css)
const AQUA_MARCA = 0x0e8f96;   // extremo "aqua" del degradado de "ORBIT" (ver automate.css)
const URL_LOGOTIPO = "/static/img/logo_canella_blanco.png";   // ruta absoluta: esto no es una plantilla

const contenedor = document.getElementById("emblemaCanella");
const canvas = contenedor && contenedor.querySelector(".emblema-esfera");
const logoPlano = contenedor && contenedor.querySelector(".emblema-marca");
if (contenedor && canvas) {
  try { iniciar(contenedor, canvas); } catch (e) { /* se queda el logotipo plano y la respiración en CSS puro */ }
}

function iniciar(contenedor, canvas) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  } catch (e) {
    return;   // sin WebGL: se queda la respiración en CSS puro (ya en el HTML/CSS)
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const escena = new THREE.Scene();
  const camara = new THREE.PerspectiveCamera(30, 1, 0.1, 10);
  camara.position.z = 4;

  // Radio apenas mayor que el marco (a esta distancia y fov, el marco mide ~1.072): que sobre lo
  // justo para no dejar ver fondo en el círculo que la recorta (.emblema), sin "acercarse" tanto
  // que se pierda la curva y el sombreado —eso fue lo que la dejó plana la primera vez—.
  const RADIO = 1.10;
  const esfera = new THREE.Mesh(
    new THREE.SphereGeometry(RADIO, 48, 32),
    new THREE.MeshPhysicalMaterial({
      color: AZUL_MARCA, metalness: 0.2, roughness: 0.32, clearcoat: 0.65, clearcoatRoughness: 0.12,
    }),
  );
  escena.add(esfera);

  // Rejilla (paralelos/meridianos) para que el giro se note aunque la luz no se moviera.
  const rejilla = new THREE.Mesh(
    new THREE.SphereGeometry(RADIO * 1.002, 12, 8),
    new THREE.MeshBasicMaterial({ color: AQUA_MARCA, wireframe: true, transparent: true, opacity: 0.24 }),
  );
  esfera.add(rejilla);

  // El logotipo, impreso sobre una porción de esfera (no un plano): sigue la misma curva que el
  // resto y lo alcanzan las mismas luces. Un pedazo pequeño de esfera, centrado justo de frente a
  // la cámara (phi y theta en π/2: ver la nota de más abajo), ancho y bajo como el logotipo.
  // Va aparte de "esfera" (no es su hijo): así no gira con ella y el texto nunca queda de canto.
  const ANCHO_LOGO = 1.5, ALTO_LOGO = 0.42;   // radianes: ~86° x ~24°, proporción parecida al logotipo
  const insignia = new THREE.Mesh(
    new THREE.SphereGeometry(
      RADIO * 1.008, 24, 8,
      Math.PI / 2 - ANCHO_LOGO / 2, ANCHO_LOGO, Math.PI / 2 - ALTO_LOGO / 2, ALTO_LOGO,
    ),
    new THREE.MeshStandardMaterial({ transparent: true, roughness: 0.55, metalness: 0.08 }),
  );
  insignia.visible = false;   // hasta que cargue la textura (si no, se ve un remiendo blanco liso)
  escena.add(insignia);
  new THREE.TextureLoader().load(URL_LOGOTIPO, (textura) => {
    textura.colorSpace = THREE.SRGBColorSpace;
    insignia.material.map = textura;
    insignia.material.needsUpdate = true;
    insignia.visible = true;
    if (logoPlano) logoPlano.hidden = true;   // ya no hace falta el logotipo plano de respaldo
  });

  // Ambiente bajo a propósito: que haya de verdad una cara oscura y una clara (si no, se ve plana).
  escena.add(new THREE.AmbientLight(0xffffff, 0.6));
  // La luz principal orbita sola (no gira con la esfera): el brillo recorre la superficie por su
  // cuenta, que es lo que más se lee como "vivo" a simple vista.
  const luzPrincipal = new THREE.DirectionalLight(0xffffff, 3.2);
  escena.add(luzPrincipal);
  // Reflejo de color en el aqua de la marca, del lado contrario: le da color al brillo sin teñir
  // el azul de fondo.
  const luzAcento = new THREE.DirectionalLight(AQUA_MARCA, 0.9);
  escena.add(luzAcento);

  function ajustarTamano() {
    const lado = contenedor.clientWidth || 120;
    renderer.setSize(lado, lado, false);   // false: el tamaño en pantalla lo decide el CSS
  }
  ajustarTamano();
  const observador = new ResizeObserver(ajustarTamano);
  observador.observe(contenedor);

  function pintar() { renderer.render(escena, camara); }

  // "Reducir movimiento" quita el desplazamiento (lo más parecido a un parallax), no la vida del
  // emblema: sigue brillando, respirando y girando, solo que sin flotar de un lado a otro.
  const reducirMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // La insignia flota hacia un destino aleatorio nuevo cada cierto tiempo, sin saltar (mismo
  // criterio de antes: velocidad independiente de los cuadros por segundo de la pantalla).
  const estado = { x: 0, y: 0 };
  const destino = { ...estado };
  const SUAVIZADO = 0.012;   // fracción del camino recorrida por cuadro a 60 fps
  let proximoCambio = 0;
  // El giro: un recorrido completo de una velocidad a otra, con curva de aceleración y frenado
  // (empieza despacio, acelera, frena despacio) en vez de "perseguir" un blanco que puede cambiar
  // a medio camino —eso último es lo que se sentía mecánico, como un motor corrigiendo el rumbo.
  // El rango es amplio (de casi quieta a un arrebato bien rápido) y a veces cambia de sentido:
  // arrebatada Y suave a la vez, porque lo suave está en la curva, no en el tamaño del cambio.
  const giro = { desde: 0.2, hasta: 0.2, valor: 0.2, inicio: 0, duracion: 1000 };
  let proximoTweenGiro = 0;
  function nuevoTweenGiro(ahora) {
    giro.desde = giro.valor;
    const sentido = Math.random() < 0.5 ? -1 : 1;
    const azar = Math.random();
    giro.hasta = azar < 0.2 ? sentido * (0.02 + Math.random() * 0.08)          // casi quieta
      : azar < 0.45 ? sentido * (1.0 + Math.random() * 0.7)                   // arrebato
      : sentido * (0.15 + Math.random() * 0.55);                             // ritmo variable
    giro.inicio = ahora;
    giro.duracion = 700 + Math.random() * 1900;   // lo que dura el recorrido en sí: rápido, no lento
    const espera = 300 + Math.random() * 1500;    // una pausa breve antes del siguiente cambio
    proximoTweenGiro = ahora + giro.duracion + espera;
  }
  // Además del giro principal, una "mirada" en los otros dos ejes: inclinaciones pequeñas y
  // aleatorias, como si la esfera mirara para un lado y para otro. Solo la esfera: la placa del
  // logotipo no tambalea con ella (crece y encoge con toda la insignia, pero no se inclina).
  const mirar = { x: 0, destinoX: 0, z: 0, destinoZ: 0 };
  let proximoCambioMirar = 0;
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
      // respira con ella (mismo valor "respiro", 0 a 1). Sigue con "reducir movimiento": es un
      // detalle pequeño de marca, no un parallax de la página.
      const respiro = (Math.sin(t * 1.5) + 1) / 2;
      const escala = 1 + respiro * 0.09 - 0.045;
      const deriva = reducirMovimiento ? "" : `translate(${estado.x}px, ${estado.y + Math.sin(t * 1.1) * 5}px) `;
      contenedor.style.transform = `${deriva}scale(${escala.toFixed(4)})`;
      contenedor.style.boxShadow =
        `0 ${(10 + respiro * 6).toFixed(1)}px ${(24 + respiro * 12).toFixed(1)}px -8px rgba(0, 0, 0, .55), ` +
        `0 0 ${(16 + respiro * 20).toFixed(1)}px ${(2 + respiro * 5).toFixed(1)}px rgba(14, 143, 150, ${(0.22 + respiro * 0.22).toFixed(3)})`;

      // El brillo orbita solo, en un recorrido suave (no un círculo perfecto: se ve más orgánico).
      luzPrincipal.position.set(Math.cos(t * 0.4) * 2.6, 1.5 + Math.sin(t * 0.63) * 1.1, 2.1 + Math.sin(t * 0.4) * 1.3);
      luzAcento.position.set(-luzPrincipal.position.x, -luzPrincipal.position.y * 0.6, 1.6);

      // La esfera gira sobre sí misma (se nota por la rejilla): cada tramo va de una velocidad a
      // otra con una curva suave de principio a fin (smoothstep), no a saltos ni corrigiendo sobre
      // la marcha.
      if (ahora >= proximoTweenGiro) nuevoTweenGiro(ahora);
      const p = Math.min((ahora - giro.inicio) / giro.duracion, 1);
      const suave = p * p * (3 - 2 * p);
      giro.valor = giro.desde + (giro.hasta - giro.desde) * suave;
      esfera.rotation.y += giro.valor * (dt / 1000);

      // La "mirada": inclinaciones pequeñas y aleatorias en los otros dos ejes, con su propio
      // ritmo (más lento que el giro, para no competir con él). Solo en la esfera: la placa del
      // logotipo no se inclina con ella (no debe tambalear), aunque sí crece y encoge junto con
      // toda la insignia, porque eso lo hace la respiración de más abajo sobre el elemento entero.
      if (ahora >= proximoCambioMirar) {
        mirar.destinoX = -0.16 + Math.random() * 0.32;
        mirar.destinoZ = -0.11 + Math.random() * 0.22;
        proximoCambioMirar = ahora + 1600 + Math.random() * 2600;
      }
      const factorMirar = 1 - Math.pow(1 - SUAVIZADO, dt / 16.7);
      mirar.x += (mirar.destinoX - mirar.x) * factorMirar;
      mirar.z += (mirar.destinoZ - mirar.z) * factorMirar;
      esfera.rotation.x = mirar.x;
      esfera.rotation.z = mirar.z;

      pintar();
    } catch (e) {
      // Cualquier error deja la respiración en CSS puro en vez de un cuadro congelado.
      contenedor.style.transform = "";
      contenedor.style.boxShadow = "";
      enPantalla = false;
      return;
    }
    if (enPantalla) cuadro = requestAnimationFrame(animar);
  }
  cuadro = requestAnimationFrame(animar);

  // Se detiene con la pestaña oculta (batería) y se limpia la memoria de la GPU al salir de la
  // página: no hace falta en un login de una sola pantalla, pero es lo correcto con WebGL.
  document.addEventListener("visibilitychange", () => {
    enPantalla = !document.hidden;
    if (enPantalla) { anterior = null; cuadro = requestAnimationFrame(animar); }
    else cancelAnimationFrame(cuadro);
  });
  window.addEventListener("pagehide", () => {
    enPantalla = false;
    cancelAnimationFrame(cuadro);
    observador.disconnect();
    esfera.geometry.dispose(); esfera.material.dispose();
    rejilla.geometry.dispose(); rejilla.material.dispose();
    insignia.geometry.dispose(); insignia.material.dispose();
    if (insignia.material.map) insignia.material.map.dispose();
    renderer.dispose();
  }, { once: true });
}
