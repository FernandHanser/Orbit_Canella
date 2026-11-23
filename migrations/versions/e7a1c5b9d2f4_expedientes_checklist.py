"""expedientes_seguros: checklist de documentos por aseguradora

Tabla EXPEDIENTES_SEGUROS_DOCUMENTOS con el checklist de Créditos de las 15 aseguradoras (hojas del
libro «CHECK DE DOCUMENTOS PARA CREDITOS»; «si aplica» = no obligatorio) y la columna
EXPEDIENTES_SEGUROS_PAQUETES.checklist, con el estado del checklist al generar cada paquete.

La ficha advierte diferencias entre ese checklist y la matriz 2026 (sección 4.1): se sembró el
checklist porque es el que usa Créditos; se ajusta desde Aseguradoras y correo.

Revision ID: e7a1c5b9d2f4
Revises: d03cd8372eae
Create Date: 2026-09-28 13:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a1c5b9d2f4'
down_revision = 'd03cd8372eae'
branch_labels = None
depends_on = None

# (aseguradora, orden, documento, obligatorio)
DOCUMENTOS = [
    ('G&T', 1, 'Factura original', True),
    ('G&T', 2, 'Orden de facturación', True),
    ('G&T', 3, 'Detalle de reparación', True),
    ('G&T', 4, 'Convenio de ajustes', True),
    ('G&T', 5, 'Presupuesto autorizado', True),
    ('G&T', 6, 'Complementos de autorizaciones', False),
    ('G&T', 7, 'Facturas de repuestos', False),
    ('G&T', 8, 'Liberación', True),
    ('G&T', 9, 'Finiquito (asegurado/tercero)', True),
    ('G&T', 10, 'Solicitud de pago', True),
    ('G&T', 11, 'Copia de tarjeta de circulación', True),
    ('G&T', 12, 'Copia de documento de identificación (DPI)', True),
    ('G&T', 13, 'Copia de pago de deducible (recibo/factura/correo)', True),
    ('G&T', 14, 'Finiquito de recolección repuestos', False),
    ('G&T', 15, 'Certificado de garantia', True),
    ('GENERAL', 1, 'Factura original', True),
    ('GENERAL', 2, 'Detalle de reparación', True),
    ('GENERAL', 3, 'Presupuesto autorizado', True),
    ('GENERAL', 4, 'Autorización de reparación', True),
    ('GENERAL', 5, 'Mitchell', True),
    ('GENERAL', 6, 'Complementos de autorizaciones', False),
    ('GENERAL', 7, 'Facturas de repuestos', False),
    ('GENERAL', 8, 'Liberación (correo y carta)', True),
    ('GENERAL', 9, 'Finiquito (asegurado/tercero)', True),
    ('GENERAL', 10, 'Copia de tarjeta de circulación', True),
    ('GENERAL', 11, 'Copia de documento de identificación (DPI)', True),
    ('GENERAL', 12, 'Copia de pago de deducible (recibo/factura/correo)', True),
    ('GENERAL', 13, 'Finiquito de recolección repuestos', False),
    ('GENERAL', 14, 'Certificado de garantia', True),
    ('MAPFRE', 1, 'Factura original', True),
    ('MAPFRE', 2, 'Detalle de reparación', True),
    ('MAPFRE', 3, 'Orión u orden de peritaje', True),
    ('MAPFRE', 4, 'Complementos de autorizaciones', False),
    ('MAPFRE', 5, 'Facturas de repuestos', False),
    ('MAPFRE', 6, 'Liberacion u Orden de entrega de vehiculo', True),
    ('MAPFRE', 7, 'Finiquito (asegurado/tercero)', True),
    ('MAPFRE', 8, 'Pantallazo de encuesta realizada', True),
    ('MAPFRE', 9, 'Copia de tarjeta de circulación', True),
    ('MAPFRE', 10, 'Copia de documento de identificación (DPI)', True),
    ('MAPFRE', 11, 'Copia de pago de deducible (recibo/factura/voucher)', True),
    ('MAPFRE', 12, 'Finiquito de recolección repuestos', False),
    ('MAPFRE', 13, 'Certificado de garantia', True),
    ('CEIBA', 1, 'Factura original', True),
    ('CEIBA', 2, 'Detalle de reparación', True),
    ('CEIBA', 3, 'Datos de ingreso a taller', True),
    ('CEIBA', 4, 'Presupuesto autorizado', True),
    ('CEIBA', 5, 'Complementos de autorizaciones', False),
    ('CEIBA', 6, 'Facturas de repuestos', False),
    ('CEIBA', 7, 'Carta de liberación', True),
    ('CEIBA', 8, 'Finiquito (asegurado/tercero)', True),
    ('CEIBA', 9, 'Encuesta', True),
    ('CEIBA', 10, 'Copia de tarjeta de circulación', True),
    ('CEIBA', 11, 'Copia de documento de identificación (DPI)', True),
    ('CEIBA', 12, 'Copia de pago de deducible y/o timbres (recibo/factura/voucher/boleta de depósito)', True),
    ('CEIBA', 13, 'Finiquito de recolección repuestos', False),
    ('CEIBA', 14, 'Certificado de garantia', True),
    ('UNIVERSALES', 1, 'Factura original', True),
    ('UNIVERSALES', 2, 'Detalle de reparación', True),
    ('UNIVERSALES', 3, 'Presupuesto autorizado', True),
    ('UNIVERSALES', 4, 'Complementos de autorizaciones', False),
    ('UNIVERSALES', 5, 'Facturas de repuestos', False),
    ('UNIVERSALES', 6, 'Liberación', True),
    ('UNIVERSALES', 7, 'Finiquito (asegurado/tercero)', True),
    ('UNIVERSALES', 8, 'Encuesta', True),
    ('UNIVERSALES', 9, 'Copia de tarjeta de circulación', True),
    ('UNIVERSALES', 10, 'Copia de documento de identificación (DPI)', True),
    ('UNIVERSALES', 11, 'Copia de pago de deducible (recibo/factura)', True),
    ('UNIVERSALES', 12, 'Recolección', True),
    ('UNIVERSALES', 13, 'Certificado de garantia', True),
    ('ROBLE', 1, 'Factura original', True),
    ('ROBLE', 2, 'Detalle de reparación', True),
    ('ROBLE', 3, 'Orden de trabajo', True),
    ('ROBLE', 4, 'Copia de pago de deducible (recibo/factura de Aseguradora)', True),
    ('ROBLE', 5, 'Presupuesto Autorizado', True),
    ('ROBLE', 6, 'Extensión de Presupuesto', False),
    ('ROBLE', 7, 'Finiquito de recolección de repuestos / Salvamento', False),
    ('ROBLE', 8, 'Encuesta', True),
    ('ROBLE', 9, 'Finiquito (asegurado / tercero)', True),
    ('ROBLE', 10, 'Copia de documento de identificación (DPI)', True),
    ('ROBLE', 11, 'Certificado de garantia', True),
    ('ROBLE', 12, 'Solicitud de repuestos', False),
    ('ROBLE', 13, 'Facturas de repuestos', False),
    ('ROBLE', 14, 'Copia de tarjeta de circulación', True),
    ('ASSA', 1, 'Factura original', True),
    ('ASSA', 2, 'Detalle de reparación', True),
    ('ASSA', 3, 'Presupuesto autorizado', True),
    ('ASSA', 4, 'Complementos de autorizaciones', False),
    ('ASSA', 5, 'Facturas de repuestos', False),
    ('ASSA', 6, 'Confirmación de datos o correo de liberación', True),
    ('ASSA', 7, 'Finiquito (asegurado/tercero)', True),
    ('ASSA', 8, 'Encuesta', True),
    ('ASSA', 9, 'Copia de tarjeta de circulación', True),
    ('ASSA', 10, 'Copia de documento de identificación (DPI)', True),
    ('ASSA', 11, 'Copia de pago de deducible (recibo/factura/transferencia/correo)', True),
    ('ASSA', 12, 'Certificado de garantia', True),
    ('AGROMERCANTIL', 1, 'Factura original', True),
    ('AGROMERCANTIL', 2, 'Detalle de reparación', True),
    ('AGROMERCANTIL', 3, 'Presupuesto autorizado', True),
    ('AGROMERCANTIL', 4, 'Complementos de autorizaciones', False),
    ('AGROMERCANTIL', 5, 'Facturas de repuestos', False),
    ('AGROMERCANTIL', 6, 'Carta de liberación', True),
    ('AGROMERCANTIL', 7, 'Finiquito (asegurado/tercero)', True),
    ('AGROMERCANTIL', 8, 'Encuesta', True),
    ('AGROMERCANTIL', 9, 'Copia de tarjeta de circulación', True),
    ('AGROMERCANTIL', 10, 'Copia de documento de identificación (DPI)', True),
    ('AGROMERCANTIL', 11, 'Copia de pago de deducible (recibo/factura)', True),
    ('AGROMERCANTIL', 12, 'Finiquito de recoleccion repuestos', False),
    ('AGROMERCANTIL', 13, 'Certificado de garantia', True),
    ('CONFIO', 1, 'Factura original', True),
    ('CONFIO', 2, 'Detalle de reparación', True),
    ('CONFIO', 3, 'Presupuesto autorizado', True),
    ('CONFIO', 4, 'Presentación de reclamo', True),
    ('CONFIO', 5, 'Complementos de autorizaciones', False),
    ('CONFIO', 6, 'Facturas de repuestos', False),
    ('CONFIO', 7, 'Correo o carta de liberación', True),
    ('CONFIO', 8, 'Finiquito (asegurado/tercero)', True),
    ('CONFIO', 9, 'Copia de tarjeta de circulación', True),
    ('CONFIO', 10, 'Copia de documento de identificación (DPI)', True),
    ('CONFIO', 11, 'Copia de pago de deducible (recibo/factura)', True),
    ('CONFIO', 12, 'Certificado de garantia', True),
    ('COLUMNA', 1, 'Factura original', True),
    ('COLUMNA', 2, 'Detalle de reparación', True),
    ('COLUMNA', 3, 'Presupuesto autorizado', True),
    ('COLUMNA', 4, 'Complementos de autorizaciones', False),
    ('COLUMNA', 5, 'Facturas de repuestos', False),
    ('COLUMNA', 6, 'Orden cerrada', True),
    ('COLUMNA', 7, 'Finiquito (asegurado/tercero)', True),
    ('COLUMNA', 8, 'Encuesta', True),
    ('COLUMNA', 9, 'Copia de tarjeta de circulación', True),
    ('COLUMNA', 10, 'Copia de documento de identificación (DPI)', True),
    ('COLUMNA', 11, 'Copia de pago de deducible/timbres (recibo/factura)', True),
    ('COLUMNA', 12, 'Certificado de garantia', True),
    ('CHN', 1, 'Factura original', True),
    ('CHN', 2, 'Detalle de reparación', True),
    ('CHN', 3, 'Presupuesto autorizado', True),
    ('CHN', 4, 'Complementos de autorizaciones', False),
    ('CHN', 5, 'Facturas de repuestos', False),
    ('CHN', 6, 'Correo o carta de liberación', True),
    ('CHN', 7, 'Finiquito (asegurado/tercero)', True),
    ('CHN', 8, 'Encuesta', True),
    ('CHN', 9, 'Copia de tarjeta de circulación', True),
    ('CHN', 10, 'Copia de documento de identificación (DPI)', True),
    ('CHN', 11, 'Copia de pago de deducible (recibo/factura)', True),
    ('CHN', 12, 'Finiquito de recolección repuestos', False),
    ('CHN', 13, 'Certificado de garantia', True),
    ('TRABAJADORES', 1, 'Factura original', True),
    ('TRABAJADORES', 2, 'Detalle de reparación', True),
    ('TRABAJADORES', 3, 'Presupuesto autorizado', True),
    ('TRABAJADORES', 4, 'Complementos de autorizaciones', False),
    ('TRABAJADORES', 5, 'Facturas de repuestos', False),
    ('TRABAJADORES', 6, 'Carta de liberación', True),
    ('TRABAJADORES', 7, 'Finiquito (asegurado/tercero)', True),
    ('TRABAJADORES', 8, 'Copia de tarjeta de circulación', True),
    ('TRABAJADORES', 9, 'Copia de documento de identificación (DPI)', True),
    ('TRABAJADORES', 10, 'Copia de pago de deducible (recibo/factura)', True),
    ('TRABAJADORES', 11, 'Finiquito de recolección repuestos', False),
    ('TRABAJADORES', 12, 'Certificado de garantia', True),
    ('RURAL', 1, 'Factura original', True),
    ('RURAL', 2, 'Check list de seguro', True),
    ('RURAL', 3, 'Detalle de reparación', True),
    ('RURAL', 4, 'Orden de ingreso al Taller', True),
    ('RURAL', 5, 'Presupuesto autorizado', True),
    ('RURAL', 6, 'Complementos de autorizaciones', False),
    ('RURAL', 7, 'Facturas de repuestos', False),
    ('RURAL', 8, 'Carta de liberación', True),
    ('RURAL', 9, 'Finiquito (asegurado/tercero)', True),
    ('RURAL', 10, 'Encuesta', True),
    ('RURAL', 11, 'Copia de tarjeta de circulación', True),
    ('RURAL', 12, 'Copia de documento de identificación (DPI)', True),
    ('RURAL', 13, 'Copia de pago de deducible (recibo/factura)', True),
    ('RURAL', 14, 'Certificado de garantia', True),
    ('GUATEMALTECA', 1, 'Factura original', True),
    ('GUATEMALTECA', 2, 'Check list de documentos para entrega de factura Taller', True),
    ('GUATEMALTECA', 3, 'Detalle de reparación', True),
    ('GUATEMALTECA', 4, 'Presupuesto autorizado', True),
    ('GUATEMALTECA', 5, 'Complementos de autorizaciones', False),
    ('GUATEMALTECA', 6, 'Facturas de repuestos y/o envió de repuestos', False),
    ('GUATEMALTECA', 7, 'Correo o carta de liberación', True),
    ('GUATEMALTECA', 8, 'Finiquito (asegurado/tercero)', True),
    ('GUATEMALTECA', 9, 'Copia de tarjeta de circulación', True),
    ('GUATEMALTECA', 10, 'Copia de documento de identificación (DPI)', True),
    ('GUATEMALTECA', 11, 'Copia de pago de deducible (recibo/factura)', True),
    ('GUATEMALTECA', 12, 'Finiquito de recolección de repuestos', False),
    ('GUATEMALTECA', 13, 'Certificado de garantia', True),
    ('FICOHSA', 1, 'Factura original', True),
    ('FICOHSA', 2, 'Detalle de reparación', True),
    ('FICOHSA', 3, 'Presupuesto autorizado', True),
    ('FICOHSA', 4, 'Convenio de reparación de talleres', True),
    ('FICOHSA', 5, 'Complementos de autorizaciones', False),
    ('FICOHSA', 6, 'Facturas de repuestos', False),
    ('FICOHSA', 7, 'Correo o carta de liberación', True),
    ('FICOHSA', 8, 'Finiquito (asegurado/tercero)', True),
    ('FICOHSA', 9, 'Encuesta', True),
    ('FICOHSA', 10, 'Copia de tarjeta de circulación', True),
    ('FICOHSA', 11, 'Copia de documento de identificación (DPI)', True),
    ('FICOHSA', 12, 'Copia de pago de deducible (recibo/factura)', True),
    ('FICOHSA', 13, 'Recolección', True),
    ('FICOHSA', 14, 'Certificado de garantia', True),
]


def _texto(valor):
    return "'" + valor.replace("'", "''") + "'"


# Cada documento apunta al id de su aseguradora: se inserta buscando por nombre (sin IDENTITY_INSERT).
# scripts/sqlserver/generar_esquema.py también los lee para 02_esquema.sql.
SQL_INICIAL = [
    "INSERT INTO EXPEDIENTES_SEGUROS_DOCUMENTOS (aseguradora_id, orden, nombre, obligatorio) "
    f"SELECT id, {orden}, {_texto(nombre)}, {1 if obligatorio else 0} "
    f"FROM EXPEDIENTES_SEGUROS_ASEGURADORAS WHERE nombre = {_texto(aseguradora)}"
    for aseguradora, orden, nombre, obligatorio in DOCUMENTOS
]


def upgrade():
    op.create_table('EXPEDIENTES_SEGUROS_DOCUMENTOS',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('aseguradora_id', sa.Integer(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=200), nullable=False),
    sa.Column('obligatorio', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['aseguradora_id'], ['EXPEDIENTES_SEGUROS_ASEGURADORAS.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_DOCUMENTOS', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_EXPEDIENTES_SEGUROS_DOCUMENTOS_aseguradora_id'), ['aseguradora_id'], unique=False)
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_PAQUETES', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checklist', sa.Text(), nullable=True))

    for sentencia in SQL_INICIAL:
        op.execute(sentencia)


def downgrade():
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_PAQUETES', schema=None) as batch_op:
        batch_op.drop_column('checklist')
    with op.batch_alter_table('EXPEDIENTES_SEGUROS_DOCUMENTOS', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_EXPEDIENTES_SEGUROS_DOCUMENTOS_aseguradora_id'))
    op.drop_table('EXPEDIENTES_SEGUROS_DOCUMENTOS')
