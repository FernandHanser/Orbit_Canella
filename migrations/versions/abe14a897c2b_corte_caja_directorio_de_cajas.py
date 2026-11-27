"""corte_caja: directorio de cajas y adjuntos de cada correo

Tablero del prototipo (commits c9f840a y 3f46741): el cuadre mensual compara los correos con el
directorio de cajas y tiendas (CORTE_CAJA_CAJAS, antes ``cajas_directorio`` en ``cajas.db``), y la
pestaña de rechazados muestra los adjuntos que llegaron (CORTE_CAJA_CORREOS.adjuntos).

Sin datos iniciales: el directorio tiene nombres y correos de personas. Se carga con
``flask --app wsgi corte_caja cajas-importar <ruta de cajas.db>``.

Revision ID: abe14a897c2b
Revises: 5869c708f797
Create Date: 2026-11-27 15:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abe14a897c2b'
down_revision = '5869c708f797'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('CORTE_CAJA_CAJAS',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('categoria', sa.String(length=100), nullable=False),
    sa.Column('nombre_caja', sa.String(length=150), nullable=False),
    sa.Column('responsable', sa.String(length=150), nullable=True),
    sa.Column('correo', sa.String(length=500), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('CORTE_CAJA_CAJAS', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_CORTE_CAJA_CAJAS_categoria'), ['categoria'], unique=False)

    with op.batch_alter_table('CORTE_CAJA_CORREOS', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adjuntos', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('CORTE_CAJA_CORREOS', schema=None) as batch_op:
        batch_op.drop_column('adjuntos')

    with op.batch_alter_table('CORTE_CAJA_CAJAS', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_CORTE_CAJA_CAJAS_categoria'))

    op.drop_table('CORTE_CAJA_CAJAS')
