# app_reservas/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import HorarioAtencion, HorarioDisponible, Negocio, Reserva, Servicio, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    # UserAdmin trae fieldsets pensados para el User por defecto (username,
    # first_name, last_name...). Como nuestro Usuario es distinto, los
    # redefinimos para que coincidan con los campos reales del modelo.
    model = Usuario
    list_display = ("email", "nombre", "rol", "activo", "is_staff", "fecha_registro")
    list_filter = ("rol", "activo", "is_staff")
    search_fields = ("email", "nombre")
    ordering = ("-fecha_registro",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información personal", {"fields": ("nombre", "telefono", "rol")}),
        ("Permisos", {"fields": ("activo", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("ultimo_login", "fecha_registro")}),
    )
    add_fieldsets = (
        (None, {
            "fields": ("email", "nombre", "rol", "password1", "password2"),
        }),
    )
    readonly_fields = ("fecha_registro",)


@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "dueno", "estado", "activo", "fecha_registro")
    list_filter = ("estado", "activo")
    search_fields = ("nombre", "direccion")


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "negocio", "precio", "activo")
    list_filter = ("negocio", "activo")


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(admin.ModelAdmin):
    list_display = ("negocio", "dia_semana", "hora_apertura", "hora_cierre", "activo")
    list_filter = ("negocio", "dia_semana")


@admin.register(HorarioDisponible)
class HorarioDisponibleAdmin(admin.ModelAdmin):
    list_display = ("negocio", "fecha", "hora", "cupo_ocupado", "cupo_maximo")
    list_filter = ("negocio", "fecha")


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("codigo_reserva", "nombre_cliente", "negocio", "fecha", "hora", "estado")
    list_filter = ("estado", "negocio", "fecha")
    search_fields = ("codigo_reserva", "nombre_cliente", "email_cliente")
    readonly_fields = ("codigo_reserva", "fecha_creacion", "fecha_actualizacion")
