# app_reservas/views.py

from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from datetime import datetime, timedelta
from django.utils import timezone
import uuid

from .forms import LoginForm, RegistroForm, ReservaForm, NegocioForm, ServicioForm, HorarioAtencionForm
from .models import (
    HorarioDisponible,
    Negocio,
    Reserva,
    Servicio,
    HorarioAtencion,
    ReservaTemporal,
)
from .permisos import solo_administrador
from .tasks import enviar_correo_confirmacion_reserva

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

# ============================================================
# NUEVA RESERVA
# ============================================================

def nueva_reserva(request, negocio_id):
    negocio = get_object_or_404(
        Negocio,
        id=negocio_id,
        activo=True
    )
    # eliminar bloqueos vencidos
    limite = timezone.now() - timedelta(minutes=5)
    ReservaTemporal.objects.filter(
        creado__lt=limite
    ).delete()

    fecha = None

    if request.method == "POST":
        fecha = request.POST.get("fecha")
    else:
        fecha = request.GET.get("fecha")
    horas_disponibles = []
    if fecha:
        for hora in HORAS_BASE:
            hora_obj = datetime.strptime(
                hora,
                "%H:%M"
            ).time()
            existe_reserva = Reserva.objects.filter(
                negocio=negocio,
                fecha=fecha,
                hora=hora_obj,
                estado=Reserva.Estado.CONFIRMADA
            ).exists()

            bloqueado = False
            temporales = ReservaTemporal.objects.filter(
                negocio=negocio,
                fecha=fecha,
                hora=hora_obj
            )

            for temp in temporales:
                if temp.esta_activa():
                    bloqueado = True
                else:
                    temp.delete()

            if not existe_reserva and not bloqueado:
                horas_disponibles.append(hora)

    # ==========================
    # GUARDAR RESERVA
    # ==========================

    if request.method == "POST":
        form = ReservaForm(
            request.POST,
            horas_disponibles=horas_disponibles
        )

        if form.is_valid():
            print(request.POST)
            print(type(form.fields["hora"]))
            print(form.fields["hora"])
            reserva = form.save(
                commit=False
            )
            reserva.negocio = negocio
            if request.user.is_authenticated:
                reserva.usuario = request.user
            reserva.estado = Reserva.Estado.CONFIRMADA

            # =================================
            # CORRECCION: GUARDAR HORA
            # =================================

            hora_seleccionada = request.POST.get(
                "hora"
            )
            if not hora_seleccionada:
                form.add_error(
                    "hora",
                    "Debe seleccionar una hora"
                )
                return render(
                    request,
                    "app_reservas/reserva_form.html",
                    {
                        "form":form,
                        "negocio":negocio,
                        "horarios":horas_disponibles
                    }
                )

            reserva.hora = datetime.strptime(
                hora_seleccionada,
                "%H:%M"
            ).time()

            # =================================
            # CODIGO DE RESERVA
            # =================================

            reserva.codigo_reserva = (
                "RES"
                +
                str(uuid.uuid4())
                .replace("-","")[:8]
                .upper()
            )

            reserva.save()

            # Envía el correo de confirmación de forma asíncrona (Celery),
            # sin bloquear la respuesta al usuario esperando al SMTP.
            enviar_correo_confirmacion_reserva.delay(reserva.id)

            # eliminar bloqueo temporal

            sesion = request.session.get(
                "sesion_id"
            )

            if sesion:
                ReservaTemporal.objects.filter(
                    usuario_sesion=sesion,
                    negocio=negocio,
                    fecha=reserva.fecha,
                    hora=reserva.hora
                ).delete()

            return redirect(
                "confirmacion_reserva",
                codigo=reserva.codigo_reserva
            )

        else:
            print("ERRORES FORMULARIO:")
            print(form.errors)
    else:
        form = ReservaForm(
            horas_disponibles=horas_disponibles
        )
    return render(
        request,
        "app_reservas/reserva_form.html",
        {
            "form":form,
            "negocio":negocio,
            "horarios":horas_disponibles
        }
    )


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

# ============================================================
# BLOQUEO TEMPORAL 5 MINUTOS
# ============================================================

def bloquear_mesa(request):
    if "sesion_id" not in request.session:
        request.session["sesion_id"] = str(
            uuid.uuid4()
        )

    hora = request.POST.get(
        "hora"
    )
    fecha = request.POST.get(
        "fecha"
    )
    negocio = request.POST.get(
        "negocio"
    )

    if not fecha or not hora:
        return JsonResponse(
            {
                "estado":"error"
            }
        )

    existentes = ReservaTemporal.objects.filter(
        negocio_id=negocio,
        fecha=fecha,
        hora=hora
    )

    for e in existentes:
        if e.esta_activa():
            return JsonResponse(
                {   
                    "estado":"ocupada"
                }
            )

        else:
            e.delete()

    ReservaTemporal.objects.create(
        negocio_id=negocio,
        fecha=fecha,
        hora=hora,
        usuario_sesion=request.session["sesion_id"]
    )

    return JsonResponse(
        {
            "estado":"ok"
        }
    )

# ============================================================
# AJAX HORARIOS DISPONIBLES
# ============================================================

def horarios_disponibles(request):
    negocio_id = request.GET.get(
        "negocio"
    )

    fecha = request.GET.get(
        "fecha"
    )

    if not fecha:
        return JsonResponse(
            {
                "horarios":[]
            }
        )
    
    horas = []
    for hora in HORAS_BASE:
        hora_obj = datetime.strptime(
            hora,
            "%H:%M"
        ).time()

        reservada = Reserva.objects.filter(
            negocio_id=negocio_id,
            fecha=fecha,
            hora=hora_obj,
            estado=Reserva.Estado.CONFIRMADA
        ).exists()

        bloqueada = ReservaTemporal.objects.filter(
            negocio_id=negocio_id,
            fecha=fecha,
            hora=hora_obj,
            creado__gte=timezone.now() - timedelta(minutes=5)
        ).exists()

        if not reservada and not bloqueada:
            horas.append(hora)
    return JsonResponse(
        {
            "horarios":horas
        }
    )
