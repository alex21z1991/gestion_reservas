# app_reservas/views.py

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoginForm, RegistroForm, ReservaForm
from .models import HorarioDisponible, Negocio, Reserva
from .permisos import solo_administrador

HORAS_BASE = ["13:00", "14:00", "15:00", "16:00", "17:00"]


# =====================================================================
#  SITIOS (index.html / sitio1.html)
# =====================================================================

def index(request):
    """Lista de negocios aprobados. Reemplaza las tarjetas fijas de index.html."""
    negocios = Negocio.objects.filter(estado=Negocio.Estado.APROBADO, activo=True)
    return render(request, "app_reservas/index.html", {"negocios": negocios})


def sitio_detalle(request, negocio_id):
    """Reemplaza sitio1.html: muestra el detalle de una sede."""
    negocio = get_object_or_404(Negocio, id=negocio_id, activo=True)
    horarios = negocio.horarios_atencion.filter(activo=True).order_by("dia_semana")
    return render(request, "app_reservas/sitio_detalle.html", {
        "negocio": negocio,
        "horarios": horarios,
    })


# =====================================================================
#  RESERVAS (reservas.html -> confir_reservas.html)
# =====================================================================

def nueva_reserva(request, negocio_id):
    negocio = get_object_or_404(Negocio, id=negocio_id, activo=True)

    if request.method == "POST":
        form = ReservaForm(request.POST, horas_disponibles=HORAS_BASE)
        if form.is_valid():
            hora = form.cleaned_data["hora"]
            fecha = form.cleaned_data["fecha"]

            with transaction.atomic():
                # Control de cupos: evita reservas duplicadas en el mismo bloque
                disponible, _ = HorarioDisponible.objects.get_or_create(
                    negocio=negocio, fecha=fecha, hora=hora,
                    defaults={"cupo_maximo": 5, "cupo_ocupado": 0},
                )
                if not disponible.disponible:
                    form.add_error(None, "Ese horario ya está completo, por favor elige otro.")
                else:
                    reserva = form.save(commit=False)
                    reserva.negocio = negocio
                    reserva.hora = hora
                    reserva.usuario = request.user if request.user.is_authenticated else None
                    reserva.estado = Reserva.Estado.CONFIRMADA
                    reserva.save()

                    disponible.cupo_ocupado += 1
                    disponible.save(update_fields=["cupo_ocupado"])

                    return redirect("confirmacion_reserva", codigo=reserva.codigo_reserva)
    else:
        form = ReservaForm(horas_disponibles=HORAS_BASE)

    return render(request, "app_reservas/reserva_form.html", {
        "form": form,
        "negocio": negocio,
    })


def confirmacion_reserva(request, codigo):
    reserva = get_object_or_404(Reserva, codigo_reserva=codigo)
    return render(request, "app_reservas/confirmacion.html", {"reserva": reserva})


# =====================================================================
#  ADMINISTRACIÓN (administracion.html)
# =====================================================================

@solo_administrador
def panel_admin(request, negocio_id):
    negocio = get_object_or_404(Negocio, id=negocio_id)
    reservas = negocio.reservas.order_by("fecha", "hora")

    contexto = {
        "negocio": negocio,
        "reservas": reservas,
        "total": reservas.count(),
        "confirmadas": reservas.filter(estado=Reserva.Estado.CONFIRMADA).count(),
        "canceladas": reservas.filter(estado=Reserva.Estado.CANCELADA).count(),
    }
    return render(request, "app_reservas/administracion.html", contexto)


@login_required
def cancelar_reserva(request, reserva_id):
    if request.method != "POST":
        return redirect("index")

    reserva = get_object_or_404(Reserva, id=reserva_id)

    # Validar que el usuario sea el dueño de la reserva o un administrador
    if not (request.user.is_administrador or reserva.usuario == request.user):
        messages.error(request, "No tienes permiso para cancelar esta reserva.")
        return redirect("index")

    if reserva.estado == Reserva.Estado.CONFIRMADA:
        reserva.cancelar()
        # Libera el cupo ocupado
        disponible = HorarioDisponible.objects.filter(
            negocio=reserva.negocio, fecha=reserva.fecha, hora=reserva.hora
        ).first()
        if disponible and disponible.cupo_ocupado > 0:
            disponible.cupo_ocupado -= 1
            disponible.save(update_fields=["cupo_ocupado"])

        messages.success(request, "La reserva fue cancelada y el horario quedó liberado.")

    if request.user.is_administrador:
        return redirect("panel_admin", negocio_id=reserva.negocio_id)
    else:
        return redirect("mis_reservas")


@login_required
def mis_reservas(request):
    """Muestra el historial de reservas del cliente autenticado."""
    reservas = request.user.reservas.order_by("-fecha", "-hora")
    
    total_reservas = reservas.count()
    activas = reservas.filter(estado=Reserva.Estado.CONFIRMADA).count()
    canceladas = reservas.filter(estado=Reserva.Estado.CANCELADA).count()

    contexto = {
        "reservas": reservas,
        "total_reservas": total_reservas,
        "activas": activas,
        "canceladas": canceladas,
    }
    return render(request, "app_reservas/mis_reservas.html", contexto)


# =====================================================================
#  CUENTA (inicio_sesion.html)
# =====================================================================

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            usuario = authenticate(
                request,
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            if usuario is not None:
                login(request, usuario)
                return redirect("index")
            form.add_error(None, "Correo o contraseña incorrectos.")
    else:
        form = LoginForm()

    return render(request, "app_reservas/login.html", {"form": form})


def registro_view(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(request, "Cuenta creada correctamente.")
            return redirect("index")
    else:
        form = RegistroForm()

    return render(request, "app_reservas/registro.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("index")
