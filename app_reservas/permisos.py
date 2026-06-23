# app_reservas/permisos.py
#
# Decoradores y mixins para controlar el acceso según el rol del
# usuario (cliente vs administrador), pensados para usarse en las
# vistas equivalentes a administracion.html / reservas.html.

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied


# ------------------ Para vistas basadas en función ------------------

def rol_requerido(*roles_permitidos):
    """
    Uso:
        @rol_requerido("administrador")
        def panel_admin(request):
            ...
    """
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if request.user.rol not in roles_permitidos:
                raise PermissionDenied("No tienes permisos para acceder a esta página.")
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


# Atajos comunes
solo_administrador = rol_requerido("administrador")
solo_dueno = rol_requerido("dueño")
solo_cliente = rol_requerido("cliente")


# ------------------ Para vistas basadas en clase (CBV) ------------------

class AdministradorRequeridoMixin(UserPassesTestMixin):
    """
    Uso:
        class PanelAdminView(AdministradorRequeridoMixin, ListView):
            model = Reserva
            ...
    """
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_administrador

    def handle_no_permission(self):
        raise PermissionDenied("Solo administradores pueden ver esta página.")


class DuenoRequeridoMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_dueno

    def handle_no_permission(self):
        raise PermissionDenied("Solo dueños de negocio pueden ver esta página.")
