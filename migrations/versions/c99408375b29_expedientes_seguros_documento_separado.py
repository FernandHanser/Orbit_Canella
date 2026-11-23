"""expedientes_seguros: "archivo aparte" por documento del checklist

Generaliza a cualquier documento del checklist lo que antes solo existía para la factura
(EXPEDIENTES_SEGUROS_ASEGURADORAS.factura_separada): ahora se gobierna por fila, desde el editor
del checklist («Archivo aparte»). Se migra el valor existente a la fila «Factura original» de cada
aseguradora y se elimina la columna de la aseguradora: una sola fuente de verdad, no dos.

Revision ID: c99408375b29
Revises: 09e8cd785ea5
Create Date: 2026-10-05 11:59:22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c99408375b29'
down_revision = '09e8cd785ea5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_DOCUMENTOS', schema=None) as batch_op:
        batch_op.add_column(sa.Column('separado', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    # El checklist puede tener más de una fila que contenga "factura original" (duplicados por
    # error, por ejemplo); se marcan todas para no perder la intención de la aseguradora.
    op.execute(
        "UPDATE EXPEDIENTES_SEGUROS_DOCUMENTOS SET separado = 1 "
        "WHERE LOWER(nombre) LIKE '%factura original%' AND aseguradora_id IN ("
        "  SELECT id FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE factura_separada = 1)"
    )

    with op.batch_alter_table('EXPEDIENTES_SEGUROS_ASEGURADORAS', schema=None) as batch_op:
        batch_op.drop_column('factura_separada')


def downgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_ASEGURADORAS', schema=None) as batch_op:
        batch_op.add_column(sa.Column('factura_separada', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    op.execute(
        "UPDATE EXPEDIENTES_SEGUROS_ASEGURADORAS SET factura_separada = 1 "
        "WHERE id IN ("
        "  SELECT aseguradora_id FROM EXPEDIENTES_SEGUROS_DOCUMENTOS "
        "  WHERE separado = 1 AND LOWER(nombre) LIKE '%factura original%')"
    )

    with op.batch_alter_table('EXPEDIENTES_SEGUROS_ASEGURADORAS', schema=None) as batch_op:
        batch_op.alter_column('factura_separada', server_default=None)

    with op.batch_alter_table('EXPEDIENTES_SEGUROS_DOCUMENTOS', schema=None) as batch_op:
        batch_op.drop_column('separado', mssql_drop_default=True)
