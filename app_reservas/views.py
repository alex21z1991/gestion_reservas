# app_reservas/views.py

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoginForm, RegistroForm, ReservaForm, NegocioForm, ServicioForm, HorarioAtencionForm
from .models import HorarioDisponible, Negocio, Reserva, Servicio, HorarioAtencion
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
    
    negocio_form = NegocioForm(instance=negocio)
    servicio_form = ServicioForm()
    horario_form = HorarioAtencionForm()
    
    active_tab = request.GET.get("tab", "reservas")
    
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit_negocio":
            negocio_form = NegocioForm(request.POST, request.FILES, instance=negocio)
            if negocio_form.is_valid():
                negocio_form.save()
                messages.success(request, "Información del local actualizada con éxito.")
                return redirect(f"/admin-reservas/{negocio_id}/?tab=info")
        elif action == "add_servicio":
            servicio_form = ServicioForm(request.POST)
            if servicio_form.is_valid():
                servicio = servicio_form.save(commit=False)
                servicio.negocio = negocio
                servicio.save()
                messages.success(request, "Servicio agregado con éxito.")
                return redirect(f"/admin-reservas/{negocio_id}/?tab=servicios")
        elif action == "add_horario":
            horario_form = HorarioAtencionForm(request.POST)
            if horario_form.is_valid():
                try:
                    horario = horario_form.save(commit=False)
                    horario.negocio = negocio
                    horario.save()
                    messages.success(request, "Horario de atención agregado con éxito.")
                except Exception as e:
                    messages.error(request, "Este día de la semana ya tiene un horario configurado.")
                return redirect(f"/admin-reservas/{negocio_id}/?tab=horarios")

    servicios = negocio.servicios.all()
    horarios = negocio.horarios_atencion.all().order_by("dia_semana")

    contexto = {
        "negocio": negocio,
        "reservas": reservas,
        "total": reservas.count(),
        "confirmadas": reservas.filter(estado=Reserva.Estado.CONFIRMADA).count(),
        "canceladas": reservas.filter(estado=Reserva.Estado.CANCELADA).count(),
        "negocio_form": negocio_form,
        "servicio_form": servicio_form,
        "horario_form": horario_form,
        "servicios": servicios,
        "horarios": horarios,
        "active_tab": active_tab,
    }
    return render(request, "app_reservas/administracion.html", contexto)


@solo_administrador
def eliminar_servicio(request, servicio_id):
    if request.method == "POST":
        servicio = get_object_or_404(Servicio, id=servicio_id)
        negocio_id = servicio.negocio_id
        servicio.delete()
        messages.success(request, "Servicio eliminado con éxito.")
        return redirect(f"/admin-reservas/{negocio_id}/?tab=servicios")
    return redirect("index")


@solo_administrador
def eliminar_horario(request, horario_id):
    if request.method == "POST":
        horario = get_object_or_404(HorarioAtencion, id=horario_id)
        negocio_id = horario.negocio_id
        horario.delete()
        messages.success(request, "Horario de atención eliminado con éxito.")
        return redirect(f"/admin-reservas/{negocio_id}/?tab=horarios")
    return redirect("index")


@login_required
def cancelar_reserva(request, reserva_id):
    if request.method != "POST":
        return redirect("index")

    reserva = get_object_or_404(Reserva, id=reserva_id)

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

    return redirect("panel_admin", negocio_id=reserva.negocio_id)


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
