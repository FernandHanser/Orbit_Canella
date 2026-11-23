/*
  ORBIT Canella — 2/2: tablas del hub en SQL Server.

  Generado por scripts/sqlserver/generar_esquema.py el 28/09/2026
  (migración de Alembic: 09e8cd785ea5). No editar a mano: regenerarlo.

  Ejecutar después de 01_crear_base.sql. Crea todas las tablas en una transacción: si algo
  falla, no queda nada a medias.
*/
USE [AUTOMATE_CANELLA];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
-- Requeridos por el índice filtrado de HUB_EJECUCIONES (sqlcmd trae QUOTED_IDENTIFIER en OFF).
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
BEGIN TRANSACTION;

CREATE TABLE [CORTE_CAJA_CORREOS] (
	id INTEGER NOT NULL IDENTITY, 
	ejecucion_id VARCHAR(32) NOT NULL, 
	message_id VARCHAR(400) NOT NULL, 
	asunto VARCHAR(500) NOT NULL, 
	remitente VARCHAR(320) NOT NULL, 
	recibido DATETIME NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	motivo VARCHAR(max) NULL, 
	empresa VARCHAR(100) NULL, 
	fecha_corte DATETIME NULL, 
	simulado BIT NOT NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX [ix_CORTE_CAJA_CORREOS_creado_en] ON [CORTE_CAJA_CORREOS] (creado_en);
CREATE INDEX [ix_CORTE_CAJA_CORREOS_ejecucion_id] ON [CORTE_CAJA_CORREOS] (ejecucion_id);
CREATE INDEX [ix_CORTE_CAJA_CORREOS_empresa] ON [CORTE_CAJA_CORREOS] (empresa);
CREATE INDEX [ix_CORTE_CAJA_CORREOS_estado] ON [CORTE_CAJA_CORREOS] (estado);
CREATE INDEX [ix_CORTE_CAJA_CORREOS_message_id] ON [CORTE_CAJA_CORREOS] (message_id);
CREATE INDEX [ix_CORTE_CAJA_CORREOS_recibido] ON [CORTE_CAJA_CORREOS] (recibido);
CREATE TABLE [CORTE_CAJA_EMPRESAS] (
	id INTEGER NOT NULL IDENTITY, 
	carpeta VARCHAR(100) NOT NULL, 
	palabras_clave VARCHAR(500) NOT NULL, 
	orden INTEGER NOT NULL, 
	activa BIT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (carpeta)
);
CREATE TABLE [EXPEDIENTES_SEGUROS_ASEGURADORAS] (
	id INTEGER NOT NULL IDENTITY, 
	nombre VARCHAR(150) NOT NULL, 
	factura_separada BIT NOT NULL, 
	para VARCHAR(1000) NULL, 
	cc VARCHAR(1000) NULL, 
	asunto VARCHAR(300) NULL, 
	cuerpo VARCHAR(max) NULL, 
	activa BIT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);
CREATE TABLE [EXPEDIENTES_SEGUROS_PAQUETES] (
	id INTEGER NOT NULL IDENTITY, 
	call_id INTEGER NOT NULL, 
	orden INTEGER NULL, 
	ceco VARCHAR(20) NULL, 
	aseguradora_codigo VARCHAR(20) NULL, 
	aseguradora_nombre VARCHAR(150) NOT NULL, 
	reclamo VARCHAR(60) NULL, 
	poliza VARCHAR(60) NULL, 
	factura_serie VARCHAR(60) NULL, 
	factura_numero VARCHAR(60) NULL, 
	anexo VARCHAR(500) NOT NULL, 
	anexo_sha256 VARCHAR(64) NOT NULL, 
	paginas VARCHAR(1000) NOT NULL, 
	cantidad_paginas INTEGER NOT NULL, 
	total_paginas INTEGER NOT NULL, 
	nombre_archivo VARCHAR(255) NOT NULL, 
	factura_separada BIT NOT NULL, 
	con_factura BIT NOT NULL, 
	para VARCHAR(1000) NOT NULL, 
	cc VARCHAR(1000) NOT NULL, 
	asunto VARCHAR(300) NOT NULL, 
	checklist VARCHAR(max) NULL, 
	segundos_armado INTEGER NULL, 
	usuario_id INTEGER NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX [ix_EXPEDIENTES_SEGUROS_PAQUETES_call_id] ON [EXPEDIENTES_SEGUROS_PAQUETES] (call_id);
CREATE INDEX [ix_EXPEDIENTES_SEGUROS_PAQUETES_creado_en] ON [EXPEDIENTES_SEGUROS_PAQUETES] (creado_en);
CREATE INDEX [ix_EXPEDIENTES_SEGUROS_PAQUETES_usuario_id] ON [EXPEDIENTES_SEGUROS_PAQUETES] (usuario_id);
CREATE TABLE [EXPEDIENTES_SEGUROS_PARAMETROS] (
	clave VARCHAR(50) NOT NULL, 
	valor VARCHAR(max) NOT NULL, 
	PRIMARY KEY (clave)
);
CREATE TABLE [HUB_INTENTOS_ACCESO] (
	id INTEGER NOT NULL IDENTITY, 
	usuario VARCHAR(100) NOT NULL, 
	ip VARCHAR(64) NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX [ix_HUB_INTENTOS_ACCESO_creado_en] ON [HUB_INTENTOS_ACCESO] (creado_en);
CREATE INDEX [ix_HUB_INTENTOS_ACCESO_ip] ON [HUB_INTENTOS_ACCESO] (ip);
CREATE INDEX [ix_HUB_INTENTOS_ACCESO_usuario] ON [HUB_INTENTOS_ACCESO] (usuario);
CREATE TABLE [HUB_MODULOS] (
	id VARCHAR(64) NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	descripcion VARCHAR(500) NOT NULL, 
	icono VARCHAR(64) NOT NULL, 
	permiso VARCHAR(100) NOT NULL, 
	activo BIT NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE [HUB_USUARIOS] (
	id INTEGER NOT NULL IDENTITY, 
	usuario_stod VARCHAR(100) NOT NULL, 
	stod_user_id VARCHAR(36) NULL, 
	nombre VARCHAR(150) NOT NULL, 
	nombres VARCHAR(100) NULL, 
	apellidos VARCHAR(100) NULL, 
	email VARCHAR(255) NULL, 
	rol VARCHAR(20) NOT NULL, 
	activo BIT NOT NULL, 
	version_sesion INTEGER NOT NULL, 
	ultimo_acceso DATETIME NULL, 
	stod_verificado_en DATETIME NULL, 
	creado_en DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX [ix_HUB_USUARIOS_usuario_stod] ON [HUB_USUARIOS] (usuario_stod);
CREATE TABLE [CORTE_CAJA_ARCHIVOS] (
	id INTEGER NOT NULL IDENTITY, 
	correo_id INTEGER NOT NULL, 
	nombre_original VARCHAR(255) NOT NULL, 
	nombre_final VARCHAR(255) NOT NULL, 
	carpeta VARCHAR(500) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	tamano INTEGER NOT NULL, 
	duplicado BIT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(correo_id) REFERENCES [CORTE_CAJA_CORREOS] (id) ON DELETE CASCADE
);
CREATE INDEX [ix_CORTE_CAJA_ARCHIVOS_correo_id] ON [CORTE_CAJA_ARCHIVOS] (correo_id);
CREATE TABLE [EXPEDIENTES_SEGUROS_CODIGOS] (
	codigo VARCHAR(20) NOT NULL, 
	aseguradora_id INTEGER NOT NULL, 
	PRIMARY KEY (codigo), 
	FOREIGN KEY(aseguradora_id) REFERENCES [EXPEDIENTES_SEGUROS_ASEGURADORAS] (id) ON DELETE CASCADE
);
CREATE INDEX [ix_EXPEDIENTES_SEGUROS_CODIGOS_aseguradora_id] ON [EXPEDIENTES_SEGUROS_CODIGOS] (aseguradora_id);
CREATE TABLE [EXPEDIENTES_SEGUROS_DOCUMENTOS] (
	id INTEGER NOT NULL IDENTITY, 
	aseguradora_id INTEGER NOT NULL, 
	orden INTEGER NOT NULL, 
	nombre VARCHAR(200) NOT NULL, 
	obligatorio BIT NOT NULL, 
	activo BIT NOT NULL DEFAULT 1, 
	PRIMARY KEY (id), 
	FOREIGN KEY(aseguradora_id) REFERENCES [EXPEDIENTES_SEGUROS_ASEGURADORAS] (id) ON DELETE CASCADE
);
CREATE INDEX [ix_EXPEDIENTES_SEGUROS_DOCUMENTOS_aseguradora_id] ON [EXPEDIENTES_SEGUROS_DOCUMENTOS] (aseguradora_id);
CREATE TABLE [HUB_EJECUCIONES] (
	id VARCHAR(32) NOT NULL, 
	modulo_id VARCHAR(64) NOT NULL, 
	tarea VARCHAR(100) NOT NULL, 
	usuario_id INTEGER NULL, 
	proceso VARCHAR(100) NULL, 
	estado VARCHAR(20) NOT NULL, 
	inicio DATETIME NOT NULL, 
	fin DATETIME NULL, 
	resultado VARCHAR(max) NULL, 
	error VARCHAR(max) NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES [HUB_USUARIOS] (id) ON DELETE SET NULL
);
CREATE INDEX [ix_HUB_EJECUCIONES_estado] ON [HUB_EJECUCIONES] (estado);
CREATE INDEX [ix_HUB_EJECUCIONES_inicio] ON [HUB_EJECUCIONES] (inicio);
CREATE INDEX [ix_HUB_EJECUCIONES_modulo_id] ON [HUB_EJECUCIONES] (modulo_id);
CREATE UNIQUE INDEX [ux_HUB_EJECUCIONES_modulo_en_curso] ON [HUB_EJECUCIONES] (modulo_id) WHERE estado = 'en_curso';
CREATE TABLE [HUB_PERMISOS_MODULO] (
	usuario_id INTEGER NOT NULL, 
	modulo_id VARCHAR(64) NOT NULL, 
	asignado_por_id INTEGER NULL, 
	asignado_en DATETIME NOT NULL, 
	PRIMARY KEY (usuario_id, modulo_id), 
	FOREIGN KEY(usuario_id) REFERENCES [HUB_USUARIOS] (id) ON DELETE CASCADE, 
	FOREIGN KEY(modulo_id) REFERENCES [HUB_MODULOS] (id) ON DELETE CASCADE, 
	FOREIGN KEY(asignado_por_id) REFERENCES [HUB_USUARIOS] (id)
);
-- Datos iniciales de CORTE_CAJA_EMPRESAS (migración b5d844416447)
INSERT INTO [CORTE_CAJA_EMPRESAS] (carpeta, palabras_clave, orden, activa) VALUES ('MAQUIPOS', 'maquipo', 10, 1);
INSERT INTO [CORTE_CAJA_EMPRESAS] (carpeta, palabras_clave, orden, activa) VALUES ('VESA', 'vesa,besa', 20, 1);
INSERT INTO [CORTE_CAJA_EMPRESAS] (carpeta, palabras_clave, orden, activa) VALUES ('Cobradores', 'colaborador,cobrador', 30, 1);
INSERT INTO [CORTE_CAJA_EMPRESAS] (carpeta, palabras_clave, orden, activa) VALUES ('Mauto', 'mauto,mantenimiento automotriz', 40, 1);
INSERT INTO [CORTE_CAJA_EMPRESAS] (carpeta, palabras_clave, orden, activa) VALUES ('MR. Credit', 'mr credit,mrcredit,mister credit', 50, 1);
INSERT INTO [CORTE_CAJA_EMPRESAS] (carpeta, palabras_clave, orden, activa) VALUES ('CANELLA', 'canella', 60, 1);
-- Datos iniciales de EXPEDIENTES_SEGUROS_PARAMETROS (migración d03cd8372eae)
INSERT INTO [EXPEDIENTES_SEGUROS_PARAMETROS] (clave, valor) VALUES ('para', 'gestrada@canella.com.gt; asistentedecobros@canella.com.gt; asistentedecobros2@canella.com.gt; cobroscanella@canella.com.gt');
INSERT INTO [EXPEDIENTES_SEGUROS_PARAMETROS] (clave, valor) VALUES ('cc', 'spintura@canella.com.gt; presupuestos.pintura2@canella.com.gt; mautofacturacion@canella.com.gt; ctoledo@canella.com.gt');
INSERT INTO [EXPEDIENTES_SEGUROS_PARAMETROS] (clave, valor) VALUES ('asunto', '{aseguradora}//Serie: {serie} Número: {numero}//CANELLA');
INSERT INTO [EXPEDIENTES_SEGUROS_PARAMETROS] (clave, valor) VALUES ('cuerpo', 'Estimados, buen día:

Adjunto documentos y factura Serie: {serie} Número: {numero}

Saludos cordiales.');
-- Datos iniciales de EXPEDIENTES_SEGUROS_ASEGURADORAS (migración d03cd8372eae)
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('G&T', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('GENERAL', 0, '{aseguradora}//Serie: {serie} Número: {numero} Reclamo:{reclamo} Póliza:{poliza} //CANELLA', 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('MAPFRE', 1, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('CEIBA', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('UNIVERSALES', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('ROBLE', 1, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('ASSA', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('AGROMERCANTIL', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('CONFIO', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('COLUMNA', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('CHN', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('TRABAJADORES', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('RURAL', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('GUATEMALTECA', 0, NULL, 1);
INSERT INTO [EXPEDIENTES_SEGUROS_ASEGURADORAS] (nombre, factura_separada, asunto, activa) VALUES ('FICOHSA', 0, NULL, 1);
-- Datos iniciales dependientes (migración d03cd8372eae)
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C002874', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C001495', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000347', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000078', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000439', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C003924', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000264', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C003922', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C003923', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C006508', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000041', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000914', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C001869', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000582', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_CODIGOS (codigo, aseguradora_id) SELECT 'C000252', id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
-- Datos iniciales dependientes (migración e7a1c5b9d2f4)
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Orden de facturación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Convenio de ajustes', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Solicitud de pago', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Copia de pago de deducible (recibo/factura/correo)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 14, 'Finiquito de recolección repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 15, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'G&T';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Autorización de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Mitchell', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Liberación (correo y carta)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Copia de pago de deducible (recibo/factura/correo)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Finiquito de recolección repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 14, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GENERAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Orión u orden de peritaje', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Liberacion u Orden de entrega de vehiculo', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Pantallazo de encuesta realizada', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura/voucher)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Finiquito de recolección repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'MAPFRE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Datos de ingreso a taller', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Copia de pago de deducible y/o timbres (recibo/factura/voucher/boleta de depósito)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Finiquito de recolección repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 14, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CEIBA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Recolección', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'UNIVERSALES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Orden de trabajo', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Copia de pago de deducible (recibo/factura de Aseguradora)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Presupuesto Autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Extensión de Presupuesto', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito de recolección de repuestos / Salvamento', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Finiquito (asegurado / tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Solicitud de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 14, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ROBLE';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Confirmación de datos o correo de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura/transferencia/correo)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'ASSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Finiquito de recoleccion repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'AGROMERCANTIL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Presentación de reclamo', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Correo o carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CONFIO';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Orden cerrada', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible/timbres (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'COLUMNA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Correo o carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Finiquito de recolección repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'CHN';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Finiquito de recolección repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'TRABAJADORES';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Check list de seguro', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Orden de ingreso al Taller', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 14, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'RURAL';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Check list de documentos para entrega de factura Taller', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Facturas de repuestos y/o envió de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Correo o carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Finiquito de recolección de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'GUATEMALTECA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 1, 'Factura original', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 2, 'Detalle de reparación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 3, 'Presupuesto autorizado', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 4, 'Convenio de reparación de talleres', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 5, 'Complementos de autorizaciones', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 6, 'Facturas de repuestos', 0 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 7, 'Correo o carta de liberación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 8, 'Finiquito (asegurado/tercero)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 9, 'Encuesta', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 10, 'Copia de tarjeta de circulación', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 11, 'Copia de documento de identificación (DPI)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 12, 'Copia de pago de deducible (recibo/factura)', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 13, 'Recolección', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';
INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) SELECT id, 14, 'Certificado de garantia', 1 FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = 'FICOHSA';

-- Versión del esquema para Alembic: las próximas migraciones parten de aquí.
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('09e8cd785ea5');

COMMIT TRANSACTION;
PRINT N'Esquema de ORBIT Canella creado (migración 09e8cd785ea5).';
GO
