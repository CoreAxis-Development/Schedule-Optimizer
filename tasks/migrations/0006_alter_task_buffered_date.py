# Generated by Django 5.0.7 on 2024-09-02 22:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0005_task_buffered_date_userprofile_safety_buffer_days'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='buffered_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
