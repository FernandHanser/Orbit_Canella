"""Modelos del núcleo: usuarios, catálogo de módulos, permisos y ejecuciones.

Las tablas del núcleo llevan el prefijo ``HUB_``; las de cada módulo, ``<ID_MODULO>_`` en
mayúsculas (p. ej. ``CORTE_CAJA_CORREOS``).

Las fechas se guardan en UTC sin zona horaria; la interfaz las muestra en hora local.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from flask_login import UserMixin

from app.core.roles import ROLES, ROLES_POR_CLAVE, Rol
from app.extensions import db


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Usuario(UserMixin, db.Model):
    """Persona que usa el hub. La identidad y la contraseña viven en STOD; aquí se guardan el
    rol, si está habilitada en el hub y sus módulos. Se crea en su primer ingreso o por
    prerregistro de un administrador."""

    __tablename__ = "HUB_USUARIOS"

    ROL_USUARIO = "usuario"
    ROL_ADMIN = "admin"
    ROL_SUPERADMIN = "superadmin"
    NOMBRES_ROL = {r.clave: r.nombre for r in ROLES}  # fuente única: app/core/roles.py

    id = db.Column(db.Integer, primary_key=True)
    usuario_stod = db.Column(db.String(100), unique=True, nullable=False, index=True)  # en minúsculas
    stod_user_id = db.Column(db.String(36), nullable=True)  # GUID de aspnet_Users
    # Derivado de STOD (correo antes de la @); se sobrescribe en cada ingreso. Solo es respaldo.
    nombre = db.Column(db.String(150), nullable=False)
    # Nombre real, registrado por un administrador (STOD no lo tiene). STOD nunca lo toca.
    nombres = db.Column(db.String(100), nullable=True)
    apellidos = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    rol = db.Column(db.String(20), nullable=False, default=ROL_USUARIO)
    # Deshabilitar en el hub bloquea el acceso aunque el usuario siga activo en STOD.
    activo = db.Column(db.Boolean, nullable=False, default=True)
    # Se incrementa al deshabilitar o cambiar el rol: invalida las sesiones abiertas.
    version_sesion = db.Column(db.Integer, nullable=False, default=1)
    ultimo_acceso = db.Column(db.DateTime, nullable=True)
    stod_verificado_en = db.Column(db.DateTime, nullable=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc)

    permisos = db.relationship(
        "PermisoModulo",
        back_populates="usuario",
        cascade="all, delete-orphan",
        foreign_keys="PermisoModulo.usuario_id",
    )

    def invalidar_sesiones(self) -> None:
        self.version_sesion = (self.version_sesion or 0) + 1

    @property
    def es_admin(self) -> bool:
        return self.rol in (self.ROL_ADMIN, self.ROL_SUPERADMIN)

    @property
    def es_superadmin(self) -> bool:
        return self.rol == self.ROL_SUPERADMIN

    @property
    def tiene_nombre_registrado(self) -> bool:
        return bool(self.nombres and self.apellidos)

    @property
    def nombre_completo(self) -> str:
        """El nombre que se muestra en el sistema. Sin nombre registrado, el derivado de STOD."""
        if self.tiene_nombre_registrado:
            return f"{self.nombres} {self.apellidos}"
        return self.nombre

    COLORES_AVATAR = ("blue", "azure", "indigo", "purple", "pink", "red", "orange", "yellow", "lime", "green", "teal", "cyan")

    @property
    def iniciales(self) -> str:
        """Primera letra del primer nombre y del primer apellido ("Juan Carlos Pérez" → "JP").
        Sin nombre registrado, las dos primeras letras del usuario STOD."""
        if self.tiene_nombre_registrado:
            return (self.nombres[0] + self.apellidos[0]).upper()
        return self.usuario_stod[:2].upper()

    @property
    def color_avatar(self) -> str:
        """Color fijo por persona (derivado del usuario STOD, que no cambia)."""
        indice = int(hashlib.sha1(self.usuario_stod.encode()).hexdigest(), 16) % len(self.COLORES_AVATAR)
        return self.COLORES_AVATAR[indice]

    @property
    def primer_nombre(self) -> str:
        return (self.nombres or self.nombre or self.usuario_stod).split(" ")[0]

    @property
    def nombre_rol(self) -> str:
        return self.NOMBRES_ROL.get(self.rol, self.rol)

    @property
    def info_rol(self) -> Rol:
        return ROLES_POR_CLAVE.get(self.rol, Rol(self.rol, self.rol, "", "secondary", False))

    @property
    def pendiente_primer_ingreso(self) -> bool:
        return self.ultimo_acceso is None

    # Flask-Login
    def get_id(self) -> str:
        return f"{self.id}:{self.version_sesion}"

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.activo)

    def modulos_ids(self) -> set[str]:
        return {p.modulo_id for p in self.permisos}

    def tiene_acceso(self, modulo_id: str) -> bool:
        return self.activo and modulo_id in self.modulos_ids()

    def __repr__(self) -> str:
        return f"<Usuario {self.usuario_stod}>"


class IntentoAcceso(db.Model):
    """Intentos fallidos de inicio de sesión, para el bloqueo temporal. Se guardan por usuario
    escrito (exista o no) e IP, así el límite aplica también antes del primer ingreso."""

    __tablename__ = "HUB_INTENTOS_ACCESO"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(100), nullable=False, index=True)
    ip = db.Column(db.String(64), nullable=True, index=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc, index=True)


class Modulo(db.Model):
    """Catálogo persistente. El código (registro) es la fuente de nombre, ícono y rutas;
    la base de datos guarda si el módulo está habilitado y a quién se asigna."""

    __tablename__ = "HUB_MODULOS"

    id = db.Column(db.String(64), primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.String(500), nullable=False, default="")
    icono = db.Column(db.String(64), nullable=False, default="puzzle")
    permiso = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc)
    actualizado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc, onupdate=ahora_utc)

    permisos = db.relationship("PermisoModulo", back_populates="modulo", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Modulo {self.id}>"


class PermisoModulo(db.Model):
    __tablename__ = "HUB_PERMISOS_MODULO"

    usuario_id = db.Column(db.Integer, db.ForeignKey("HUB_USUARIOS.id", ondelete="CASCADE"), primary_key=True)
    modulo_id = db.Column(db.String(64), db.ForeignKey("HUB_MODULOS.id", ondelete="CASCADE"), primary_key=True)
    # Sin acción en cascada: SQL Server no admite dos rutas en cascada hacia HUB_USUARIOS desde esta
    # tabla (usuario_id ya es CASCADE). El hub no borra usuarios, solo los deshabilita.
    asignado_por_id = db.Column(db.Integer, db.ForeignKey("HUB_USUARIOS.id"), nullable=True)
    asignado_en = db.Column(db.DateTime, nullable=False, default=ahora_utc)

    usuario = db.relationship("Usuario", back_populates="permisos", foreign_keys=[usuario_id])
    modulo = db.relationship("Modulo", back_populates="permisos")


class Ejecucion(db.Model):
    """Registro común de ejecuciones de automatizaciones (web, CLI o programadas)."""

    __tablename__ = "HUB_EJECUCIONES"
    # Mutex de ejecución: la base garantiza a lo sumo una ejecución "en_curso" por módulo,
    # aunque dos procesos intenten iniciar al mismo tiempo (índice único filtrado).
    __table_args__ = (
        db.Index(
            "ux_HUB_EJECUCIONES_modulo_en_curso", "modulo_id", unique=True,
            mssql_where=db.text("estado = 'en_curso'"), sqlite_where=db.text("estado = 'en_curso'"),
        ),
    )

    ESTADOS = ("en_curso", "exito", "advertencia", "sin_cambios", "error", "interrumpida")
    # Los que una tarea puede fijar en ctx.estado. "sin_cambios": no había nada que procesar
    # (típico de tareas programadas que revisan algo cada pocos minutos); se purgan solas.
    ESTADOS_FINALES_TAREA = ("exito", "advertencia", "sin_cambios")

    id = db.Column(db.String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    modulo_id = db.Column(db.String(64), nullable=False, index=True)
    tarea = db.Column(db.String(100), nullable=False, default="")
    usuario_id = db.Column(db.Integer, db.ForeignKey("HUB_USUARIOS.id", ondelete="SET NULL"), nullable=True)
    proceso = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(20), nullable=False, default="en_curso", index=True)
    inicio = db.Column(db.DateTime, nullable=False, default=ahora_utc, index=True)
    fin = db.Column(db.DateTime, nullable=True)
    resultado = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)

    usuario = db.relationship("Usuario")

    @property
    def iniciado_por(self) -> str:
        if self.usuario is not None:
            return self.usuario.nombre_completo
        if self.proceso:
            return f"proceso: {self.proceso}"
        return "desconocido"

    @property
    def duracion_segundos(self) -> float | None:
        if self.fin is None:
            return None
        return (self.fin - self.inicio).total_seconds()

    def __repr__(self) -> str:
        return f"<Ejecucion {self.id} {self.modulo_id}:{self.tarea} {self.estado}>"
