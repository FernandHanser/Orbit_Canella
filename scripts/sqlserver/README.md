# Base de datos del hub en SQL Server

| Archivo | Qué hace |
|---|---|
| `01_crear_base.sql` | Crea la base `AUTOMATE_CANELLA` (`Modern_Spanish_CI_AS`). Si ya existe, no hace nada |
| `02_esquema.sql` | Crea las tablas del hub en `AUTOMATE_CANELLA` y marca la versión de Alembic |
| `generar_esquema.py` | Regenera `02_esquema.sql` desde los modelos, tras cada migración nueva |

Los dos `.sql` son T-SQL normal: se abren en SSMS y se ejecutan tal cual, en orden. Probados en
SQL Server LocalDB con el hub completo (login, módulos, ejecuciones, paginación, API y tildes).

Los logins y permisos los administra el DBA del servidor. El login que use el hub necesita en
`AUTOMATE_CANELLA`: `db_datareader` y `db_datawriter` para operar, y `db_ddladmin` si el hub
aplicará sus propias migraciones al publicar módulos nuevos (si no, el DBA las aplica con el SQL
que genera `flask --app wsgi db upgrade --sql`).

## Conectar el hub

En `.env` (si la contraseña tiene símbolos como `@`, `:` o `/`, codificarla para URL; en Python:
`urllib.parse.quote_plus`):

```
DATABASE_URL=mssql+pyodbc://<login>:<contraseña>@SERVIDOR/AUTOMATE_CANELLA?driver=ODBC+Driver+17+for+SQL+Server
```

Instancia con nombre: `SERVIDOR\INSTANCIA` se escribe `SERVIDOR%5CINSTANCIA`. Con autenticación de
Windows: `mssql+pyodbc://@SERVIDOR/AUTOMATE_CANELLA?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes`.

Después, verificar, dar de alta al superadministrador y reiniciar el servidor del hub:

```bash
flask --app wsgi db current        # la última migración con "(head)"
flask --app wsgi db check          # "No new upgrade operations detected."
flask --app wsgi usuarios superadmin fhanser
```

Alternativa a `02_esquema.sql`: con el `.env` apuntando a la base vacía,
`flask --app wsgi db upgrade` crea las mismas tablas aplicando las migraciones.

## Nombres

| Objeto | Convención | Ejemplo |
|---|---|---|
| Base de datos | `AUTOMATE_CANELLA` | — |
| Tablas del núcleo | Prefijo `HUB_`, mayúsculas | `HUB_USUARIOS`, `HUB_MODULOS`, `HUB_PERMISOS_MODULO`, `HUB_EJECUCIONES`, `HUB_INTENTOS_ACCESO` |
| Tablas de un módulo | Prefijo `<ID_MODULO>_`, mayúsculas | `CORTE_CAJA_CORREOS`, `CONTRASENAS_TRAMITES` |
| Control de versiones del esquema | `alembic_version` (nombre fijo de Alembic) | — |

## Mantenimiento

- **Módulos nuevos con tablas**: se agregan con migraciones (`flask --app wsgi db migrate` y
  `db upgrade`). Después, regenerar `02_esquema.sql` con `python scripts/sqlserver/generar_esquema.py`.
- **Datos iniciales**: `02_esquema.sql` crea las tablas desde los modelos, no aplica migraciones.
  Los datos que siembra una migración se declaran en su constante `DATOS_INICIALES` y el
  generador los agrega como `INSERT` (hoy: las empresas de `CORTE_CAJA_EMPRESAS` y las aseguradoras
  y el correo por defecto de `EXPEDIENTES_SEGUROS_*`). Las filas que dependen de otras van en
  `SQL_INICIAL` y se agregan después.

## Compatibilidad con SQL Server (para quien escriba código)

- `HUB_EJECUCIONES` tiene un índice único **filtrado** (`WHERE estado = 'en_curso'`). SQL Server
  exige `ANSI_NULLS ON` y `QUOTED_IDENTIFIER ON` para crearlo y para escribir en la tabla: SSMS y
  pyodbc los activan por defecto, `02_esquema.sql` los fija y con `sqlcmd` no hace falta nada más.
- Filtros booleanos con `columna == True`, no `columna.is_(True)`: SQL Server no acepta `IS 1`.
- Una tabla no puede tener dos llaves foráneas con `ON DELETE CASCADE`/`SET NULL` hacia la
  misma tabla (error de "multiple cascade paths"); dejar una sin acción.
- `db.Text` se crea como `VARCHAR(MAX)`; las cadenas son `VARCHAR` con la intercalación de la
  base, que admite tildes y ñ.
