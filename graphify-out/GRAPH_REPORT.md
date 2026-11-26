# Graph Report - AUTOMATE_CANELLA  (2026-11-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1507 nodes · 3527 edges · 80 communities (57 shown, 23 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 300 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e85ab7f4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 72

## God Nodes (most connected - your core abstractions)
1. `Usuario` - 86 edges
2. `crear_usuario()` - 48 edges
3. `Ejecucion` - 43 edges
4. `Paquete` - 37 edges
5. `get_logger()` - 36 edges
6. `ejecutar_tarea()` - 32 edges
7. `create_app()` - 31 edges
8. `Modulo` - 29 edges
9. `Aseguradora` - 25 edges
10. `Empresa` - 25 edges

## Surprising Connections (you probably didn't know these)
- `test_admin_no_cambia_roles_ni_se_deshabilita()` --uses--> `Usuario`  [INFERRED]
  tests/test_acceso.py → app/core/models.py
- `test_superadmin_no_se_modifica_por_la_web()` --uses--> `Usuario`  [INFERRED]
  tests/test_acceso.py → app/core/models.py
- `test_cli_tareas_y_superadmin()` --uses--> `Usuario`  [INFERRED]
  tests/test_logs_ejecuciones.py → app/core/models.py
- `test_autorizado_ejecuta_tarea_web()` --uses--> `Ejecucion`  [INFERRED]
  tests/test_acceso.py → app/core/models.py
- `test_modulo_deshabilitado_no_disponible()` --uses--> `Modulo`  [INFERRED]
  tests/test_acceso.py → app/core/models.py

## Import Cycles
- 2-file cycle: `app/modulos/corte_caja/__init__.py -> app/modulos/corte_caja/empresas.py -> app/modulos/corte_caja/__init__.py`
- 2-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/aseguradoras.py -> app/modulos/expedientes_seguros/__init__.py`
- 2-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/cli.py -> app/modulos/expedientes_seguros/__init__.py`
- 3-file cycle: `app/modulos/corte_caja/__init__.py -> app/modulos/corte_caja/cli.py -> app/modulos/corte_caja/views.py -> app/modulos/corte_caja/__init__.py`
- 3-file cycle: `app/modulos/corte_caja/__init__.py -> app/modulos/corte_caja/empresas.py -> app/modulos/corte_caja/views.py -> app/modulos/corte_caja/__init__.py`
- 3-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/aseguradoras.py -> app/modulos/expedientes_seguros/servicios.py -> app/modulos/expedientes_seguros/__init__.py`
- 3-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/aseguradoras.py -> app/modulos/expedientes_seguros/views.py -> app/modulos/expedientes_seguros/__init__.py`
- 3-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/cli.py -> app/modulos/expedientes_seguros/views.py -> app/modulos/expedientes_seguros/__init__.py`
- 4-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/aseguradoras.py -> app/modulos/expedientes_seguros/views.py -> app/modulos/expedientes_seguros/servicios.py -> app/modulos/expedientes_seguros/__init__.py`
- 4-file cycle: `app/modulos/expedientes_seguros/__init__.py -> app/modulos/expedientes_seguros/cli.py -> app/modulos/expedientes_seguros/views.py -> app/modulos/expedientes_seguros/servicios.py -> app/modulos/expedientes_seguros/__init__.py`

## Communities (80 total, 23 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (39): _ahora_utc(), CodigoAseguradora, Documento, Paquete, checklist_de(), anchos(), cajero(), ceiba_con_checklist() (+31 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (25): stod(), _cliente(), _input(), test_acceso_foco_en_usuario_al_abrir(), test_acceso_permite_mostrar_la_contrasena(), test_actualiza_datos_desde_stod(), test_admin_asigna_y_retira_acceso(), test_admin_deshabilita_usuario_y_cierra_su_sesion() (+17 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (22): solo_administradores(), aseguradora_editar(), aseguradora_eliminar(), aseguradora_nueva(), aseguradoras(), checklist(), _codigos(), _errores_checklist() (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (25): ConfigSap, Anexo, Factura, _fecha(), Llamada, Pendiente, RepositorioSap, SapNoDisponible (+17 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (28): Adjunto, aplicar_plantilla(), correo_eml(), correo_invalido(), correo_saliente(), direcciones(), es_dpi(), es_factura() (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (33): mantenimiento_al_iniciar(), Ejecucion, _ejecucion_con_error(), _ejecucion_en_curso(), _ejecucion_sin_cambios(), _eventos(), test_accesos_denegados_quedan_registrados(), test_accesos_http_no_llenan_el_log_central() (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (27): carpeta_destino(), Clasificacion, clasificar(), dominio(), Empresa, Error, es_adjunto_ignorable(), es_mensaje_automatico() (+19 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (27): _aplicar_permisos(), _contexto_admin(), ejecucion_detalle(), ejecuciones(), logs(), modulo_estado(), modulos(), modulos_sincronizar() (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (14): es_administrador(), _datos(), empresa_editar(), empresa_eliminar(), empresa_nueva(), empresas(), FormEmpresa, limpiar_claves() (+6 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (8): ArchivoGuardado, sha256(), Buzon, BuzonEws, Correo, Archivo, html_rechazo(), _Procesador

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (34): alembic_version, CORTE_CAJA_ARCHIVOS, CORTE_CAJA_CORREOS, CORTE_CAJA_EMPRESAS, EXPEDIENTES_SEGUROS_ASEGURADORAS, EXPEDIENTES_SEGUROS_CODIGOS, EXPEDIENTES_SEGUROS_DOCUMENTOS, EXPEDIENTES_SEGUROS_PAQUETES (+26 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (19): armar(), concatenar(), contar_paginas(), imagen_pagina(), leer(), PdfInvalido, sha256(), mapa_paginas() (+11 more)

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (13): instalar(), listar_usuarios(), logs_buscar(), modulos_listar(), modulos_sincronizar(), quitar_superadmin(), superadmin(), tareas_ejecutar() (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (21): _carpetas_de_modulos(), _id_declarado(), _imports(), _modifica_configuracion_comun(), _nombre(), _resolver(), _tablas(), test_cada_modulo_tiene_sus_pruebas() (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.07
Nodes (29): concurrency, cancel-in-progress, group, name, needs, runs-on, steps, timeout-minutes (+21 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (16): modo_envio(), CorreoNoEnviado, Enviador, Parametro, adjuntos_de(), _ahora(), carpeta_paquete(), crear_enviador() (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (12): EjecucionEnCurso, ejecutar_tarea(), ResumenEjecucion, ultimas_ejecuciones(), procesar_ahora(), crear_ejecucion(), estado(), ejecutar() (+4 more)

### Community 17 - "Community 17"
Cohesion: 0.19
Nodes (24): actualizarChecklist(), actualizarContador(), alternar(), asignar(), asignarPorAsignar(), avisarCompleto(), cancelarTodo(), cerrarYIr() (+16 more)

### Community 18 - "Community 18"
Cohesion: 0.13
Nodes (19): aseguradora_de(), checklist(), correo_sugerido(), datos_plantilla(), buscar(), _cargar(), correo(), descargar() (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.14
Nodes (16): revalidar_sesion(), controlar_acceso(), instalar(), respuesta_denegada(), respuesta_modulo_no_disponible(), respuesta_no_autenticado(), envoltura(), es_peticion_api() (+8 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (11): configurar_logging(), ContextoFilter, _hora_local(), JsonFormatter, _modulo_desde_registro(), _nivel_num(), sanear_datos(), SinAccesosHttpFilter (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.10
Nodes (23): crear_usuario(), entrar(), test_admin_no_deshabilita_a_otro_admin(), test_bloqueo_por_intentos_incluso_sin_usuario_local(), test_contrasena_incorrecta(), test_csrf_activo_en_formularios_y_api(), test_deshabilitado_en_hub_no_entra(), test_inactivo_en_stod_no_entra() (+15 more)

### Community 22 - "Community 22"
Cohesion: 0.19
Nodes (21): Adjunto, Correo, correo(), procesar(), test_admin_crea_edita_y_elimina_empresas(), test_boton_revisar_buzon(), test_configuracion_incompleta_falla_con_mensaje_claro(), test_correo_invalido_se_rechaza_solo_al_remitente_y_escapado() (+13 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (8): probar_correo(), ConfigCorreo, EnviadorSmtp, _explicar(), _temporal(), _config_correo(), test_smtp_reintenta_las_fallas_temporales_y_no_las_definitivas(), test_smtp_starttls_y_autentica_antes_de_enviar()

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (3): Usuario, Rol, test_iniciales_y_color_estable()

### Community 25 - "Community 25"
Cohesion: 0.17
Nodes (11): acceso(), _bloqueado(), cargar_usuario(), _ip(), _registrar_fallo(), sincronizar_usuario(), FormAcceso, ahora_utc() (+3 more)

### Community 26 - "Community 26"
Cohesion: 0.17
Nodes (13): ejecucion(), _en_curso(), _iniciar(), marcar_interrumpidas(), _rechazar(), _serializar(), establecer_ejecucion(), establecer_usuario() (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.13
Nodes (12): ceco_por_defecto(), ConfiguracionIncompleta, correo(), _identificador(), retencion_dias(), sap(), servidor_anexos(), _valor() (+4 more)

### Community 28 - "Community 28"
Cohesion: 0.18
Nodes (5): Identidad, normalizar_usuario(), ProveedorSimulado, ProveedorStod, test_nombre_visible()

### Community 29 - "Community 29"
Cohesion: 0.15
Nodes (4): sincronizar_si_hay_esquema(), url_pagina(), create_app(), _instalar_plantillas()

### Community 30 - "Community 30"
Cohesion: 0.16
Nodes (7): IdentidadNoDisponible, _cadena_conexion(), conexion_stod(), instalar(), StodNoDisponible, verificar_hash_membership(), test_verificacion_hash_membership()

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (9): _informe_md(), main(), _nombre_archivo(), recorrer(), _ruta(), crear_app_qa(), main(), _olvidar_env_real() (+1 more)

### Community 32 - "Community 32"
Cohesion: 0.16
Nodes (6): ModuloDisponible, modulos_de_usuario(), inicio(), salud(), Tarjeta, _contexto()

### Community 33 - "Community 33"
Cohesion: 0.16
Nodes (10): sincronizar_catalogo(), admin(), app(), autorizado(), client(), contar_consultas(), entrar_como(), _entrar() (+2 more)

### Community 34 - "Community 34"
Cohesion: 0.18
Nodes (5): cargar_modulos(), DefinicionModulo, _descubrir(), RegistroModulos, test_definicion_de_modulo_validada()

### Community 35 - "Community 35"
Cohesion: 0.16
Nodes (8): aislar_peticiones(), _mover(), test_api_con_sesion_vencida_responde_401(), test_consultar_estado_no_cuenta_como_actividad(), test_extender_renueva_la_inactividad(), test_formulario_con_sesion_vencida_lleva_al_login_y_no_a_un_400(), test_inactividad_cierra_con_motivo_y_vuelve_a_la_pagina(), test_la_actividad_renueva_y_la_jornada_no()

### Community 37 - "Community 37"
Cohesion: 0.17
Nodes (8): salir(), sesion_estado(), sesion_extender(), inactividad_s(), iniciar(), maxima_s(), restante(), verificar()

### Community 38 - "Community 38"
Cohesion: 0.17
Nodes (6): test_con_bom_para_powershell_5(), test_el_puerto_interno_lo_pone_el_instalador(), test_el_workflow_despliega_solo_si_pasan_las_pruebas(), test_instala_todos_los_requirements(), test_powershell_sin_errores_de_sintaxis(), _valor()

### Community 39 - "Community 39"
Cohesion: 0.23
Nodes (5): Archivador, _candidatos(), _sha256_archivo(), test_archivador_no_duplica_el_mismo_contenido(), test_archivador_no_sale_de_la_raiz()

### Community 40 - "Community 40"
Cohesion: 0.21
Nodes (8): Configuracion, ConfiguracionIncompleta, leer(), modo_actual(), _valor(), crear_archivador(), crear_buzon(), procesar()

### Community 41 - "Community 41"
Cohesion: 0.15
Nodes (5): contenedor, iniciar(), animar(), pintar(), TINTE

### Community 42 - "Community 42"
Cohesion: 0.32
Nodes (7): _abrir_edicion_del_operador(), _elegir_rol(), _opcion(), _rol_en_base(), test_confirmar_si_da_el_rol_de_administrador(), test_guardar_sin_tocar_el_rol_no_pide_confirmacion(), test_marcar_administrador_pide_confirmacion_y_cancelar_no_guarda_nada()

### Community 43 - "Community 43"
Cohesion: 0.24
Nodes (5): _buscar(), empresa_agregar(), empresa_modificar(), empresas(), _registrar()

### Community 44 - "Community 44"
Cohesion: 0.19
Nodes (5): Assert-Salida(), Find-Python(), Get-VersionPython(), Install-Servicio(), Write-Hecho()

### Community 45 - "Community 45"
Cohesion: 0.18
Nodes (5): errores_js(), servidor(), servidor_aparte(), _crear(), ServidorQA

### Community 46 - "Community 46"
Cohesion: 0.24
Nodes (4): incluir_en_migracion(), _diferencias(), test_ignora_tablas_de_modulos_no_cargados(), test_sigue_detectando_tablas_nuevas_de_los_modulos_cargados()

### Community 47 - "Community 47"
Cohesion: 0.35
Nodes (9): registro(), _pedir(), _rutas_de_modulos(), test_hay_modulos_y_rutas_que_revisar(), test_ninguna_ruta_de_un_modulo_responde_sin_sesion(), test_ninguna_ruta_de_un_modulo_responde_sin_tenerlo_asignado(), test_tener_modulos_asignados_no_abre_la_administracion(), test_un_modulo_deshabilitado_no_responde_ni_a_quien_lo_tiene_asignado() (+1 more)

### Community 48 - "Community 48"
Cohesion: 0.39
Nodes (8): entrar(), test_aviso_de_sesion_por_vencer_y_extender(), test_deshabilitar_un_modulo_pide_confirmacion_y_cancelar_no_cambia_nada(), test_login_correcto_lleva_al_inicio_sin_errores_js(), test_login_incorrecto_avisa_en_espanol_y_no_entra(), test_ojo_muestra_y_oculta_la_contrasena(), test_operador_entra_a_un_modulo_asignado(), test_sin_modulo_asignado_ve_acceso_denegado()

### Community 50 - "Community 50"
Cohesion: 0.27
Nodes (7): _bool(), Config, DevelopmentConfig, _env(), _lista(), ProductionConfig, TestingConfig

### Community 51 - "Community 51"
Cohesion: 0.18
Nodes (6): _exigir_habilitado(), ModuloDeshabilitado, get_logger(), test_logs_abre_sin_debug_y_todos_lo_incluye(), test_no_se_registran_contrasenas(), test_paginacion_de_logs()

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (3): test_los_botones_del_encabezado_no_tapan_el_titulo(), test_database_url_es_obligatoria(), test_proveedor_simulado_solo_en_pruebas()

### Community 54 - "Community 54"
Cohesion: 0.25
Nodes (4): opciones_servidor(), test_con_proxy_confia_en_su_ip_real_y_https(), test_sin_variables_escucha_solo_en_el_equipo(), test_variables_vacias_usan_los_valores_por_defecto()

### Community 56 - "Community 56"
Cohesion: 0.44
Nodes (9): consultar(), entendido(), extender(), formato(), guardar(), mostrar(), ocultar(), salir() (+1 more)

### Community 57 - "Community 57"
Cohesion: 0.42
Nodes (7): agregar(), avisar(), destinatarios(), pintar(), separar(), sincronizar(), valor()

### Community 60 - "Community 60"
Cohesion: 0.32
Nodes (5): contenedor, iniciar(), animar(), nuevoTweenGiro(), pintar()

### Community 61 - "Community 61"
Cohesion: 0.36
Nodes (5): confirmar(), mostrarCargando(), mostrarPantalla(), pedirConfirmacion(), spinner()

### Community 64 - "Community 64"
Cohesion: 0.29
Nodes (3): BuzonNoDisponible, _usar_proxy(), send()

## Knowledge Gaps
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Usuario` connect `Community 24` to `Community 32`, `Community 33`, `Community 1`, `Community 0`, `Community 36`, `Community 3`, `Community 5`, `Community 7`, `Community 42`, `Community 12`, `Community 15`, `Community 21`, `Community 22`, `Community 25`, `Community 31`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 50 inferred relationships involving `Usuario` (e.g. with `_aplicar_permisos()` and `puede_cambiar_estado()`) actually correct?**
  _`Usuario` has 50 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05009009009009009 - nodes in this community are weakly interconnected._
- **Why does `get_logger()` connect `Community 51` to `Community 32`, `Community 2`, `Community 34`, `Community 5`, `Community 37`, `Community 7`, `Community 8`, `Community 43`, `Community 12`, `Community 15`, `Community 16`, `Community 18`, `Community 19`, `Community 20`, `Community 25`, `Community 26`, `Community 29`, `Community 30`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `Ejecucion` (e.g. with `ejecucion_detalle()` and `ejecuciones()`) actually correct?**
  _`Ejecucion` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.04558737580362361 - nodes in this community are weakly interconnected._
- **Why does `crear_usuario()` connect `Community 21` to `Community 0`, `Community 33`, `Community 1`, `Community 3`, `Community 36`, `Community 7`, `Community 47`, `Community 15`, `Community 22`, `Community 24`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._