# Generated by Django 4.2.20 on 2025-03-24 20:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrule', '0005_auto_20230802_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='rrule',
            name='time_last_handled',
            field=models.DateTimeField(default=None, null=True),
        ),
    ]
