from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from app_reservas.models import Negocio, Reserva, HorarioDisponible
import datetime

Usuario = get_user_model()

class ReservasClientesTestCase(TestCase):
    def setUp(self):
        # Crear usuarios
        self.cliente1 = Usuario.objects.create_user(
            email="cliente1@test.com",
            nombre="Cliente Uno",
            password="password123",
            rol=Usuario.Rol.CLIENTE
        )
        self.cliente2 = Usuario.objects.create_user(
            email="cliente2@test.com",
            nombre="Cliente Dos",
            password="password123",
            rol=Usuario.Rol.CLIENTE
        )
        self.admin = Usuario.objects.create_superuser(
            email="admin@test.com",
            nombre="Administrador",
            password="password123"
        )
        
        # Crear negocio
        self.negocio = Negocio.objects.create(
            nombre="Restaurante Test",
            estado=Negocio.Estado.APROBADO,
            activo=True
        )
        
        # Crear disponibilidad
        self.fecha = datetime.date.today() + datetime.timedelta(days=5)
        self.hora = datetime.time(13, 0)
        self.disponible = HorarioDisponible.objects.create(
            negocio=self.negocio,
            fecha=self.fecha,
            hora=self.hora,
            cupo_maximo=5,
            cupo_ocupado=1
        )
        
        # Crear reserva
        self.reserva = Reserva.objects.create(
            usuario=self.cliente1,
            negocio=self.negocio,
            nombre_cliente="Cliente Uno",
            email_cliente="cliente1@test.com",
            telefono_cliente="+56912345678",
            fecha=self.fecha,
            hora=self.hora,
            comensales=2,
            estado=Reserva.Estado.CONFIRMADA
        )

    def test_ver_mis_reservas_autenticado(self):
        # Iniciar sesión con cliente1
        self.client.login(email="cliente1@test.com", password="password123")
        response = self.client.get(reverse("mis_reservas"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Uno")
        self.assertContains(response, self.reserva.codigo_reserva)

    def test_ver_mis_reservas_anonimo(self):
        # Usuario no autenticado debe redirigir a login
        response = self.client.get(reverse("mis_reservas"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/cuenta/login/", response.url)

    def test_cancelar_propia_reserva(self):
        self.client.login(email="cliente1@test.com", password="password123")
        
        # Guardar estado inicial de cupo ocupado
        self.assertEqual(self.disponible.cupo_ocupado, 1)
        
        # Cancelar
        response = self.client.post(reverse("cancelar_reserva", args=[self.reserva.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("mis_reservas"))
        
        # Verificar estado
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)
        
        # Verificar liberación de cupo
        self.disponible.refresh_from_db()
        self.assertEqual(self.disponible.cupo_ocupado, 0)

    def test_cancelar_reserva_ajena_denegado(self):
        # Intentar cancelar con cliente2
        self.client.login(email="cliente2@test.com", password="password123")
        
        response = self.client.post(reverse("cancelar_reserva", args=[self.reserva.id]))
        self.assertEqual(response.status_code, 302)
        
        # La reserva debe seguir CONFIRMADA
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CONFIRMADA)

    def test_admin_puede_cancelar_cualquiera(self):
        self.client.login(email="admin@test.com", password="password123")
        
        response = self.client.post(reverse("cancelar_reserva", args=[self.reserva.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("panel_admin", args=[self.negocio.id]))
        
        # Verificar estado
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)
