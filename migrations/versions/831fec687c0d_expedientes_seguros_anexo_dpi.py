"""expedientes_seguros: evidencia del DPI a color en el paquete

El expediente de la llamada puede traer, además del PDF principal, un segundo anexo en SAP con el
DPI a color (``ATC1``, mismo origen, nombre empezando en «DPI»: ver ``reglas.es_dpi``). Cuando el
paquete se armó con ese anexo combinado, se guarda su ruta y hash igual que ya se hace con el
expediente, para la misma evidencia de qué archivo original se usó.

Revision ID: 831fec687c0d
Revises: c99408375b29
Create Date: 2026-10-05 12:40:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '831fec687c0d'
down_revision = 'c99408375b29'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_PAQUETES', schema=None) as batch_op:
        batch_op.add_column(sa.Column('anexo_dpi', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('anexo_dpi_sha256', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_PAQUETES', schema=None) as batch_op:
        batch_op.drop_column('anexo_dpi_sha256')
        batch_op.drop_column('anexo_dpi')
