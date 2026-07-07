# app_reservas/forms.py

import re
from datetime import date, timedelta

from django import forms

from .models import Reserva, Usuario


class ReservaForm(forms.ModelForm):

    hora = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    class Meta:
        model = Reserva
        fields = [
            "nombre_cliente",
            "email_cliente",
            "telefono_cliente",
            "fecha",
            "comensales",
            "ocasion",
            "notas",
        ]
        widgets = {
            "nombre_cliente": forms.TextInput(attrs={
                "class": "form-control custom-input",
                "placeholder": "Benjamin Flores Gonzalez",
            }),
            "email_cliente": forms.EmailInput(attrs={
                "class": "form-control custom-input",
                "placeholder": "benjamin@email.com",
            }),
            "telefono_cliente": forms.TextInput(attrs={
                "class": "form-control custom-input",
                "placeholder": "+56 9 XXXX XXXX",
            }),
            "fecha": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control custom-input",
            }),
            "comensales": forms.Select(attrs={
                "class": "form-select custom-input"
            }),
            "ocasion": forms.Select(attrs={
                "class": "form-select custom-input"
            }),
            "notas": forms.Textarea(attrs={
                "class": "form-control custom-input",
                "rows": 3,
            }),
        }

    def __init__(self, *args, horas_disponibles=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["comensales"].widget.choices = [
            (i, f"{i} persona" if i == 1 else f"{i} personas")
            for i in range(1, 8)
        ] + [(8, "8 o más personas")]

    def clean_telefono_cliente(self):
        telefono = self.cleaned_data["telefono_cliente"]
        digitos = re.sub(r"\D", "", telefono)

        if digitos.startswith("56") and len(digitos) == 11:
            digitos = digitos[2:]

        if not re.match(r"^9\d{8}$", digitos):
            raise forms.ValidationError(
                "Ingresa un número válido de 9 dígitos (ej: 9XXXXXXXX)."
            )
        return f"+56{digitos}"

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        hoy = date.today()
        fecha_max = hoy + timedelta(days=90)

        if fecha < hoy:
            raise forms.ValidationError("Seleccione una fecha válida (no puede ser en el pasado).")
        if fecha > fecha_max:
            raise forms.ValidationError("Solo se permiten reservas hasta 90 días en el futuro.")
        return fecha


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Correo",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "********"}),
    )


class RegistroForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "********"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "********"}),
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "telefono"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre completo"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "+56 9 XXXX XXXX"}),
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        usuario.rol = Usuario.Rol.CLIENTE
        if commit:
            usuario.save()
        return usuario
