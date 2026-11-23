# ORBIT Canella — guía para asistentes de código

Hub Flask de automatizaciones contables de Canella. **Monolito modular**: `app/core/` (núcleo),
`app/integraciones/` (sistemas externos compartidos) y `app/modulos/<id>/` (una carpeta por
automatización). Todo en español: código, comentarios, documentación y mensajes de commit.

## Antes de cambiar algo

1. [docs/MAPA.md](docs/MAPA.md): dónde vive cada cosa.
2. [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): reglas y porqué. Si vas a crear un módulo,
   [docs/AGREGAR_MODULO.md](docs/AGREGAR_MODULO.md).
3. La guía del módulo que vas a tocar (tabla «Guías» del [README](README.md)).

## Comandos

```bash
python -m pytest                          # todo, en segundos; SQLite en memoria y STOD simulado
python -m pytest tests/test_arquitectura.py
flask --app wsgi run --debug              # servidor real en :5000 (usa la base de .env)
flask --app wsgi db migrate -m "<id>: qué cambia"   # revisar SIEMPRE el archivo generado
flask --app wsgi db upgrade
```

## Reglas que no se negocian

- **Dependencias:** `core` no importa `modulos` ni `integraciones`; un módulo no importa otro
  módulo ni `app.core.models`. Lo verifica `tests/test_arquitectura.py`: si falla, se corrige el
  diseño, no la prueba.
- **Contrato del núcleo para módulos:** `DefinicionModulo`, `get_logger`, `ejecucion`,
  `ejecutar_tarea`, `ultimas_ejecuciones`, `es_administrador`, `solo_administradores`,
  paginación y `db`. Nada más.
- **Tablas:** `HUB_*` el núcleo, `<ID_MODULO>_*` cada módulo. Un módulo no nombra tablas `HUB_*`
  (guarda `usuario_id` / `ejecucion_id` como enteros, sin `ForeignKey`).
- **Plantillas** de un módulo en `templates/<id>/`; extienden `base.html`. Sin JavaScript en
  línea (CSP): scripts en archivos y comportamiento con atributos `data-*`.
- **Tareas:** sin `db.session.commit()` dentro de una tarea; efectos externos (correo, archivos,
  SAP) al final e idempotentes. Ver ARQUITECTURA.md#atomicidad.
- **Configuración de un módulo:** variables `<MODULO>_*` en `.env`, leídas por el propio módulo
  al usarse. Nunca en `app/config.py`.
- **Sistemas externos** (SAP, Exchange, SMTP, carpetas de red) detrás de un contrato (`Protocol`)
  con su implementación real aparte, para simularlos en pruebas.

## Cuidado

- **No se versionan** `.env`, `instance/`, `contexto/` ni `logs/`: tienen secretos o datos
  personales (DPI, expedientes, correos reales).
- **No conectar a las bases reales** (AUTOMATE_CANELLA en 128.1.200.70, STOD, SAP) ni aplicar
  migraciones allí sin que el responsable lo pida: darle los comandos exactos.
- Para ver una pantalla sin la base real: un servidor aparte con `create_app("testing", ...)`,
  SQLite temporal y usuario del STOD simulado, en otro puerto (p. ej. 5057). Nunca el de :5000.
- Toda funcionalidad nueva lleva prueba, y todo cambio de comportamiento se documenta en la guía
  que corresponda (`docs/`).

## Git

Ramas `main` (producción) y `dev` (trabajo). Los cambios van a `dev`; a `main` solo lo probado.
