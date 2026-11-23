"""expedientes_seguros: envío del correo desde el buzón del hub

El paquete se puede enviar por SMTP desde el hub (además del borrador .eml). Se guarda cuándo y
quién lo envió para no mandarlo dos veces.

Revision ID: 5e2b9c4d7a10
Revises: 831fec687c0d
Create Date: 2026-10-22 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e2b9c4d7a10'
down_revision = '831fec687c0d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_PAQUETES', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enviado_en', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('enviado_por', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_PAQUETES', schema=None) as batch_op:
        batch_op.drop_column('enviado_por')
        batch_op.drop_column('enviado_en')
