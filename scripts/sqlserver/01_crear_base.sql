/*
  ORBIT Canella — 1/2: crea la base de datos AUTOMATE_CANELLA.

  Solo crea la base. Los logins y permisos los administra el DBA del servidor.
  Después ejecutar 02_esquema.sql.
*/
IF DB_ID(N'AUTOMATE_CANELLA') IS NULL
    CREATE DATABASE [AUTOMATE_CANELLA] COLLATE Modern_Spanish_CI_AS;
GO
