# Generated by Django 4.2.20 on 2025-03-24 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrule', '0005_auto_20230802_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='rrule',
            name='time_last_handled',
            field=models.DateTimeField(db_index=True, default=None, null=True),
        ),
    ]
