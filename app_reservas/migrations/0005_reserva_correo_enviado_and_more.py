# Generated manually for app_reservas, siguiendo el estilo de las migraciones previas.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_reservas', '0004_reservatemporal'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='correo_enviado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reserva',
            name='correo_enviado_fecha',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reserva',
            name='correo_error',
            field=models.TextField(blank=True, null=True),
        ),
    ]
