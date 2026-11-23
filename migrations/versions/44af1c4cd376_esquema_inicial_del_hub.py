"""esquema inicial del hub

Tablas del núcleo con prefijo HUB_. Consolida las migraciones previas al primer despliegue
(24/09/2026): identidad por usuario de STOD, roles, intentos de acceso, catálogo de módulos,
permisos por persona y ejecuciones. Compatible con SQLite y SQL Server.

Revision ID: 44af1c4cd376
Revises: 
Create Date: 2026-09-24 19:42:08.249810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '44af1c4cd376'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('HUB_INTENTOS_ACCESO',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario', sa.String(length=100), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('HUB_INTENTOS_ACCESO', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_HUB_INTENTOS_ACCESO_creado_en'), ['creado_en'], unique=False)
        batch_op.create_index(batch_op.f('ix_HUB_INTENTOS_ACCESO_ip'), ['ip'], unique=False)
        batch_op.create_index(batch_op.f('ix_HUB_INTENTOS_ACCESO_usuario'), ['usuario'], unique=False)

    op.create_table('HUB_MODULOS',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('descripcion', sa.String(length=500), nullable=False),
    sa.Column('icono', sa.String(length=64), nullable=False),
    sa.Column('permiso', sa.String(length=100), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('HUB_USUARIOS',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_stod', sa.String(length=100), nullable=False),
    sa.Column('stod_user_id', sa.String(length=36), nullable=True),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('rol', sa.String(length=20), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('version_sesion', sa.Integer(), nullable=False),
    sa.Column('ultimo_acceso', sa.DateTime(), nullable=True),
    sa.Column('stod_verificado_en', sa.DateTime(), nullable=True),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('HUB_USUARIOS', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_HUB_USUARIOS_usuario_stod'), ['usuario_stod'], unique=True)

    op.create_table('HUB_EJECUCIONES',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('modulo_id', sa.String(length=64), nullable=False),
    sa.Column('tarea', sa.String(length=100), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('proceso', sa.String(length=100), nullable=True),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('inicio', sa.DateTime(), nullable=False),
    sa.Column('fin', sa.DateTime(), nullable=True),
    sa.Column('resultado', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['HUB_USUARIOS.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('HUB_EJECUCIONES', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_HUB_EJECUCIONES_estado'), ['estado'], unique=False)
        batch_op.create_index(batch_op.f('ix_HUB_EJECUCIONES_inicio'), ['inicio'], unique=False)
        batch_op.create_index(batch_op.f('ix_HUB_EJECUCIONES_modulo_id'), ['modulo_id'], unique=False)

    op.create_table('HUB_PERMISOS_MODULO',
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('modulo_id', sa.String(length=64), nullable=False),
    sa.Column('asignado_por_id', sa.Integer(), nullable=True),
    sa.Column('asignado_en', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['asignado_por_id'], ['HUB_USUARIOS.id'], ),
    sa.ForeignKeyConstraint(['modulo_id'], ['HUB_MODULOS.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['HUB_USUARIOS.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('usuario_id', 'modulo_id')
    )


def downgrade():
    op.drop_table('HUB_PERMISOS_MODULO')
    with op.batch_alter_table('HUB_EJECUCIONES', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_HUB_EJECUCIONES_modulo_id'))
        batch_op.drop_index(batch_op.f('ix_HUB_EJECUCIONES_inicio'))
        batch_op.drop_index(batch_op.f('ix_HUB_EJECUCIONES_estado'))

    op.drop_table('HUB_EJECUCIONES')
    with op.batch_alter_table('HUB_USUARIOS', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_HUB_USUARIOS_usuario_stod'))

    op.drop_table('HUB_USUARIOS')
    op.drop_table('HUB_MODULOS')
    with op.batch_alter_table('HUB_INTENTOS_ACCESO', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_HUB_INTENTOS_ACCESO_usuario'))
        batch_op.drop_index(batch_op.f('ix_HUB_INTENTOS_ACCESO_ip'))
        batch_op.drop_index(batch_op.f('ix_HUB_INTENTOS_ACCESO_creado_en'))

    op.drop_table('HUB_INTENTOS_ACCESO')
