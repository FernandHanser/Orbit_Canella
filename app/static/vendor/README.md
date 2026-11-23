# Recursos de terceros (servidos localmente)

| Paquete | Versión fijada | Licencia | Archivos incluidos |
|---|---|---|---|
| [@tabler/core](https://github.com/tabler/tabler) | 1.5.1 | MIT | `tabler-1.5.1/css/tabler.min.css`, `tabler-1.5.1/js/tabler.min.js` |
| [@tabler/icons-webfont](https://github.com/tabler/tabler-icons) | 3.48.0 | MIT | `tabler-icons-3.48.0/tabler-icons.min.css`, `fonts/tabler-icons.woff2` (el CSS también declara `.woff` y `.ttf`; se omitieron porque todos los navegadores soportados usan `.woff2`) |
| [Oxanium](https://github.com/sevmeyer/oxanium) (vía @fontsource/oxanium) | 5.3.0 | OFL-1.1 | `oxanium-5.3.0/oxanium-latin-800-normal.woff2` (palabra "ORBIT" del login) |
| [three.js](https://github.com/mrdoob/three.js) | 0.180.0 | MIT | `three-0.180.0/build/three.module.min.js` y `three.core.min.js` (el primero importa el segundo: van juntos) — solo para el respaldo `static/js/emblema-esfera-3d.js` (esfera 3D anterior del login; hoy no se carga) |
| [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs) | 0.3.2 | MIT | `thinking-orbs-0.3.2/engine.es.js` e `index-B8WsUNf5.js` (el primero importa el segundo: van juntos; es el motor sin React) y `LICENSE` — orb del emblema del login, `static/js/emblema-canella.js` |

No se incluyen ApexCharts, plugins opcionales, páginas de demostración ni mapas de código
(se eliminó la referencia `sourceMappingURL` para evitar peticiones 404).

Para actualizar: `npm pack @tabler/core@<versión> @tabler/icons-webfont@<versión>`, copiar los
mismos archivos a una carpeta nueva con la versión en el nombre y cambiar las rutas en
`app/templates/base_layout.html`.
