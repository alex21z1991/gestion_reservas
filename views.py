from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from datetime import datetime, timedelta
from django.utils import timezone
import uuid

from .forms import LoginForm, RegistroForm, ReservaForm

from .models import (
    HorarioDisponible,
    Negocio,
    Reserva,
    ReservaTemporal
)

from .permisos import solo_administrador


HORAS_BASE = [
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00"
]


# ============================================================
# INDEX
# ============================================================

def index(request):

    negocios = Negocio.objects.filter(
        estado=Negocio.Estado.APROBADO,
        activo=True
    )

    return render(
        request,
        "app_reservas/index.html",
        {
            "negocios": negocios
        }
    )



# ============================================================
# DETALLE SITIO
# ============================================================

def sitio_detalle(request, negocio_id):

    negocio = get_object_or_404(
        Negocio,
        id=negocio_id,
        activo=True
    )

    horarios = negocio.horarios_atencion.filter(
        activo=True
    )

    return render(
        request,
        "app_reservas/sitio_detalle.html",
        {
            "negocio": negocio,
            "horarios": horarios
        }
    )



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




# ============================================================
# CONFIRMACION
# ============================================================

def confirmacion_reserva(request, codigo):


    reserva = get_object_or_404(

        Reserva,

        codigo_reserva=codigo

    )


    return render(

        request,

        "app_reservas/confirmacion.html",

        {

            "reserva":reserva

        }

    )
# ============================================================
# ADMIN
# ============================================================


@solo_administrador

def panel_admin(request, negocio_id):


    negocio = get_object_or_404(

        Negocio,

        id=negocio_id

    )


    reservas = negocio.reservas.order_by(

        "fecha",

        "hora"

    )



    return render(

        request,

        "app_reservas/administracion.html",

        {

            "negocio":negocio,

            "reservas":reservas,

            "total":reservas.count(),

            "confirmadas":
                reservas.filter(
                    estado=Reserva.Estado.CONFIRMADA
                ).count(),

            "canceladas":
                reservas.filter(
                    estado=Reserva.Estado.CANCELADA
                ).count()

        }

    )





# ============================================================
# CANCELAR RESERVA
# ============================================================


@login_required

def cancelar_reserva(request, reserva_id):


    reserva = get_object_or_404(

        Reserva,

        id=reserva_id

    )


    reserva.cancelar()


    messages.success(

        request,

        "Reserva cancelada"

    )


    return redirect(

        "panel_admin",

        negocio_id=reserva.negocio_id

    )





# ============================================================
# LOGIN
# ============================================================


def login_view(request):


    if request.method == "POST":


        form = LoginForm(request.POST)



        if form.is_valid():


            usuario = authenticate(

                request,

                email=form.cleaned_data["email"],

                password=form.cleaned_data["password"]

            )



            if usuario:


                login(

                    request,

                    usuario

                )


                return redirect(
                    "index"
                )



    else:


        form = LoginForm()



    return render(

        request,

        "app_reservas/login.html",

        {

            "form":form

        }

    )






# ============================================================
# REGISTRO
# ============================================================


def registro_view(request):


    if request.method == "POST":


        form = RegistroForm(request.POST)



        if form.is_valid():


            usuario = form.save()


            login(

                request,

                usuario

            )


            return redirect(
                "index"
            )



    else:


        form = RegistroForm()



    return render(

        request,

        "app_reservas/registro.html",

        {

            "form":form

        }

    )






# ============================================================
# LOGOUT
# ============================================================


@login_required

def logout_view(request):


    logout(request)


    return redirect(
        "index"
    )






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