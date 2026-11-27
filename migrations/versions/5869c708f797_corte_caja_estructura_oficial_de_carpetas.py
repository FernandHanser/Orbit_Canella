"""corte_caja: estructura oficial de carpetas

El prototipo pasó a la estructura oficial de producción el 03/11/2026 (commit 083118e): cada
empresa guarda sus cortes en subcarpetas con formato propio y con el nombre de carpeta que ya usa
Contabilidad. Se agrega ``plantilla_carpeta`` a CORTE_CAJA_EMPRESAS y se actualizan las seis
empresas sembradas en b5d844416447:

    Canella        Canella\\1.Año2026\\202611NOVIEMBRE\\27-11-26
    Mauto          Mauto\\1.Año2026\\11 NOVIEMBRE 2026\\27-11-26
    las demás      Vesa\\1.Año 2026\\202611NOVIEMBRE\\27-11-26

Los nombres MAQUIPOS, VESA, MR. Credit y CANELLA pasan a Maquipos, Vesa, Mister Credit y Canella
(también en el historial de CORTE_CAJA_CORREOS, para que el filtro por empresa los siga
encontrando). Si un administrador ya cambió una empresa desde el panel, su fila no coincide con
el WHERE y no se toca.

Revision ID: 5869c708f797
Revises: 5e2b9c4d7a10
Create Date: 2026-11-27 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5869c708f797'
down_revision = '5e2b9c4d7a10'
branch_labels = None
depends_on = None

ESTANDAR = '1.Año {AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}'
CANELLA = '1.Año{AAAA}/{AAAA}{MM}{MES}/{DD}-{MM}-{AA}'
MAUTO = '1.Año{AAAA}/{MM} {MES} {AAAA}/{DD}-{MM}-{AA}'

# (nombre sembrado en b5d844416447, nombre oficial)
RENOMBRES = [('MAQUIPOS', 'Maquipos'), ('VESA', 'Vesa'), ('MR. Credit', 'Mister Credit'), ('CANELLA', 'Canella')]

# scripts/sqlserver/generar_esquema.py también aplica estas sentencias después de los datos iniciales.
SQL_INICIAL = [
    *(f"UPDATE CORTE_CAJA_EMPRESAS SET carpeta = '{nuevo}' WHERE carpeta = '{viejo}'" for viejo, nuevo in RENOMBRES),
    f"UPDATE CORTE_CAJA_EMPRESAS SET plantilla_carpeta = '{CANELLA}' WHERE carpeta = 'Canella'",
    f"UPDATE CORTE_CAJA_EMPRESAS SET plantilla_carpeta = '{MAUTO}' WHERE carpeta = 'Mauto'",
    *(f"UPDATE CORTE_CAJA_CORREOS SET empresa = '{nuevo}' WHERE empresa = '{viejo}'" for viejo, nuevo in RENOMBRES),
]


def upgrade():
    with op.batch_alter_table('CORTE_CAJA_EMPRESAS', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plantilla_carpeta', sa.String(length=200), nullable=False, server_default=ESTANDAR))
    for sentencia in SQL_INICIAL:
        op.execute(sentencia)


def downgrade():
    for viejo, nuevo in RENOMBRES:
        op.execute(f"UPDATE CORTE_CAJA_CORREOS SET empresa = '{viejo}' WHERE empresa = '{nuevo}'")
        op.execute(f"UPDATE CORTE_CAJA_EMPRESAS SET carpeta = '{viejo}' WHERE carpeta = '{nuevo}'")
    with op.batch_alter_table('CORTE_CAJA_EMPRESAS', schema=None) as batch_op:
        batch_op.drop_column('plantilla_carpeta')
