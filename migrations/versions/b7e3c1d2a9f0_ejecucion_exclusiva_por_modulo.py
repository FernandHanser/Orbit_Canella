"""ejecución exclusiva por módulo

Índice único filtrado: a lo sumo una ejecución "en_curso" por módulo. La base lo garantiza
aunque dos procesos intenten iniciar al mismo tiempo. Antes de crearlo, si un módulo ya tiene
varias "en_curso", se conserva la más reciente y las demás se marcan "interrumpida" (si no,
el índice no podría crearse).

Revision ID: b7e3c1d2a9f0
Revises: 44af1c4cd376
Create Date: 2026-09-25 12:00:00.000000

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e3c1d2a9f0'
down_revision = '44af1c4cd376'
branch_labels = None
depends_on = None

INDICE = 'ux_HUB_EJECUCIONES_modulo_en_curso'
MENSAJE = ("Interrumpida al activar la ejecución exclusiva: el módulo tenía otra ejecución "
           "en curso más reciente.")


def upgrade():
    conexion = op.get_bind()
    filas = conexion.execute(sa.text(
        "SELECT id, modulo_id FROM HUB_EJECUCIONES WHERE estado = 'en_curso' "
        "ORDER BY modulo_id, inicio DESC, id DESC"
    )).fetchall()
    vistos, sobrantes = set(), []
    for id_, modulo_id in filas:
        if modulo_id in vistos:
            sobrantes.append(id_)
        vistos.add(modulo_id)
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    for id_ in sobrantes:
        conexion.execute(
            sa.text("UPDATE HUB_EJECUCIONES SET estado = 'interrumpida', fin = :fin, error = :error WHERE id = :id"),
            {"fin": ahora, "error": MENSAJE, "id": id_},
        )

    with op.batch_alter_table('HUB_EJECUCIONES', schema=None) as batch_op:
        batch_op.create_index(
            INDICE, ['modulo_id'], unique=True,
            mssql_where=sa.text("estado = 'en_curso'"), sqlite_where=sa.text("estado = 'en_curso'"),
        )


def downgrade():
    with op.batch_alter_table('HUB_EJECUCIONES', schema=None) as batch_op:
        batch_op.drop_index(INDICE)
