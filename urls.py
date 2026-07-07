from django.urls import path
from . import views


urlpatterns = [

    path(
        "",
        views.index,
        name="index"
    ),

    path(
        "sitio/<int:negocio_id>/",
        views.sitio_detalle,
        name="sitio_detalle"
    ),

    path(
        "sitio/<int:negocio_id>/reservar/",
        views.nueva_reserva,
        name="nueva_reserva"
    ),

    path(
        "reserva/<str:codigo>/confirmacion/",
        views.confirmacion_reserva,
        name="confirmacion_reserva"
    ),

    path(
        "admin-reservas/<int:negocio_id>/",
        views.panel_admin,
        name="panel_admin"
    ),

    path(
        "admin-reservas/cancelar/<int:reserva_id>/",
        views.cancelar_reserva,
        name="cancelar_reserva"
    ),

    path(
        "cuenta/login/",
        views.login_view,
        name="login"
    ),

    path(
        "cuenta/registro/",
        views.registro_view,
        name="registro"
    ),

    path(
        "cuenta/logout/",
        views.logout_view,
        name="logout"
    ),

    path(
        "bloquear-mesa/",
        views.bloquear_mesa,
        name="bloquear_mesa"
    ),

    path(
        "horarios-disponibles/",
        views.horarios_disponibles,
        name="horarios_disponibles"
    ),
]