# app_reservas/tasks.py

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo_confirmacion_reserva(self, reserva_id):
    """
    Envía el correo de confirmación al email_cliente de una reserva y
    deja registrado en la propia tabla `reservas` (MySQL) si se envió
    correctamente o no.

    Se llama de forma asíncrona (con .delay()) justo después de guardar
    la reserva en views.nueva_reserva, para no bloquear la respuesta al
    usuario mientras se conecta al servidor SMTP.
    """
    # Import local: evita problemas de "apps not loaded" cuando el
    # worker de Celery arranca antes que el registro de apps de Django.
    from .models import Reserva

    try:
        reserva = Reserva.objects.select_related("negocio").get(id=reserva_id)
    except Reserva.DoesNotExist:
        # Si la reserva ya no existe (por ejemplo se canceló y se borró
        # justo después de crearse), no tiene sentido reintentar.
        return f"Reserva {reserva_id} no encontrada, no se envía correo."

    asunto = f"Reserva confirmada en {reserva.negocio.nombre} - {reserva.codigo_reserva}"

    contexto = {"reserva": reserva}
    html_contenido = render_to_string("app_reservas/email_confirmacion.html", contexto)
    texto_plano = strip_tags(html_contenido)

    try:
        send_mail(
            subject=asunto,
            message=texto_plano,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[reserva.email_cliente],
            html_message=html_contenido,
            fail_silently=False,
        )
    except Exception as exc:
        # Deja registrado el último error en MySQL, aunque todavía se
        # vaya a reintentar (así el admin puede ver que algo falló sin
        # esperar a que se agoten los reintentos).
        reserva.correo_error = str(exc)
        reserva.save(update_fields=["correo_error"])

        # Reintenta (hasta 3 veces, cada 60s) ante fallos temporales de
        # red o del servidor SMTP, en vez de perder el correo.
        raise self.retry(exc=exc)

    # Envío exitoso: se guarda en la tabla `reservas` de MySQL.
    reserva.correo_enviado = True
    reserva.correo_enviado_fecha = timezone.now()
    reserva.correo_error = None
    reserva.save(update_fields=["correo_enviado", "correo_enviado_fecha", "correo_error"])

    return f"Correo de confirmación enviado a {reserva.email_cliente} ({reserva.codigo_reserva})"
