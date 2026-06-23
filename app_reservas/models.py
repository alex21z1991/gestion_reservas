# app_reservas/models.py
#
# Modelos de Django para ClickyGo, alineados 1 a 1 con clickygo_schema.sql
#
# IMPORTANTE - elige UNA de estas dos formas de trabajar:
#   A) Dejar que Django cree las tablas (recomendado):
#        - Deja managed = True (valor por defecto, ya está abajo).
#        - NO ejecutes clickygo_schema.sql.
#        - Corre: python manage.py makemigrations && python manage.py migrate
#
#   B) Usar el script SQL ya creado (clickygo_schema.sql) y que Django solo
#      "lea" esas tablas existentes:
#        - Ejecuta primero clickygo_schema.sql en MySQL.
#        - Cambia managed = True a managed = False en cada Meta.
#        - Corre: python manage.py migrate --fake app_reservas
#
# Este archivo asume managed=True (opción A) porque es la forma estándar y
# más segura de trabajar con Django + MySQL.

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


# =====================================================================
#  USUARIOS Y ROLES (cliente / administrador / dueño)
# =====================================================================

class UsuarioManager(BaseUserManager):
    """Manager personalizado: el login se hace con email, no con username."""

    def create_user(self, email, nombre, password=None, rol="cliente", **extra_fields):
        if not email:
            raise ValueError("El usuario debe tener un correo electrónico.")
        email = self.normalize_email(email)
        usuario = self.model(email=email, nombre=nombre, rol=rol, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, nombre, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", Usuario.Rol.ADMINISTRADOR)
        return self.create_user(email, nombre, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de usuario único para los 3 roles del sistema.
    Se referencia en settings.py como AUTH_USER_MODEL = 'app_reservas.Usuario'.
    """

    class Rol(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        ADMINISTRADOR = "administrador", "Administrador"
        DUENO = "dueño", "Dueño de negocio"

    nombre = models.CharField(max_length=150)
    email = models.EmailField(max_length=150, unique=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CLIENTE)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    ultimo_login = models.DateTimeField(null=True, blank=True)

    # Campos requeridos por Django para el sistema de auth/permisos
    is_staff = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        db_table = "usuarios"
        managed = True

    def __str__(self):
        return f"{self.nombre} ({self.rol})"

    @property
    def is_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    @property
    def is_dueno(self):
        return self.rol == self.Rol.DUENO

    @property
    def is_cliente(self):
        return self.rol == self.Rol.CLIENTE


# =====================================================================
#  NEGOCIOS (Sedes / Sitios)
# =====================================================================

class Negocio(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    dueno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="negocios",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    email_contacto = models.EmailField(max_length=150, null=True, blank=True)
    imagen_url = models.CharField(max_length=255, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "negocios"
        managed = True

    def __str__(self):
        return self.nombre


# =====================================================================
#  SERVICIOS
# =====================================================================

class Servicio(models.Model):
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="servicios")
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "servicios"
        managed = True

    def __str__(self):
        return f"{self.nombre} - {self.negocio.nombre}"


# =====================================================================
#  HORARIOS DE ATENCIÓN (semanal, general por negocio)
# =====================================================================

class HorarioAtencion(models.Model):
    class Dia(models.IntegerChoices):
        DOMINGO = 0, "Domingo"
        LUNES = 1, "Lunes"
        MARTES = 2, "Martes"
        MIERCOLES = 3, "Miércoles"
        JUEVES = 4, "Jueves"
        VIERNES = 5, "Viernes"
        SABADO = 6, "Sábado"

    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="horarios_atencion")
    dia_semana = models.IntegerField(choices=Dia.choices)
    hora_apertura = models.TimeField()
    hora_cierre = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "horarios_atencion"
        managed = True
        unique_together = ("negocio", "dia_semana")

    def __str__(self):
        return f"{self.negocio.nombre} - {self.get_dia_semana_display()}"


# =====================================================================
#  HORARIOS DISPONIBLES (cupos por bloque horario / fecha)
#  Corresponde a los botones de hora 13:00-17:00 en reservas.html
# =====================================================================

class HorarioDisponible(models.Model):
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="disponibilidad")
    fecha = models.DateField()
    hora = models.TimeField()
    cupo_maximo = models.PositiveSmallIntegerField(default=1)
    cupo_ocupado = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "horarios_disponibles"
        managed = True
        unique_together = ("negocio", "fecha", "hora")

    @property
    def disponible(self):
        return self.cupo_ocupado < self.cupo_maximo

    def __str__(self):
        return f"{self.negocio.nombre} - {self.fecha} {self.hora}"


# =====================================================================
#  RESERVAS
#  Refleja exactamente los campos usados en reservas.html,
#  confir_reservas.html y administracion.html
# =====================================================================

class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        CONFIRMADA = "Confirmada", "Confirmada"
        CANCELADA = "Cancelada", "Cancelada"

    class Ocasion(models.TextChoices):
        NINGUNA = "Ninguna", "Ninguna"
        CUMPLEANOS = "Cumpleaños", "Cumpleaños"
        ANIVERSARIO = "Aniversario", "Aniversario"
        OTRO = "Otro", "Otro"

    codigo_reserva = models.CharField(max_length=20, unique=True, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas",
    )
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name="reservas")

    nombre_cliente = models.CharField(max_length=150)
    email_cliente = models.EmailField(max_length=150)
    telefono_cliente = models.CharField(max_length=20)

    fecha = models.DateField()
    hora = models.TimeField()
    comensales = models.PositiveSmallIntegerField()
    ocasion = models.CharField(max_length=50, choices=Ocasion.choices, default=Ocasion.NINGUNA)
    notas = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.CONFIRMADA)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reservas"
        managed = True
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["negocio", "fecha"]),
        ]

    def save(self, *args, **kwargs):
        # Genera el código corto tipo RRS-XXX, igual al usado en
        # administracion.html / confir_reservas.html
        if not self.codigo_reserva:
            import time
            self.codigo_reserva = f"RRS-{str(int(time.time()))[-3:]}"
        super().save(*args, **kwargs)

    def cancelar(self):
        self.estado = self.Estado.CANCELADA
        self.save(update_fields=["estado", "fecha_actualizacion"])

    def __str__(self):
        return f"{self.codigo_reserva} - {self.nombre_cliente} ({self.estado})"
