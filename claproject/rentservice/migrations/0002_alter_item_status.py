# Generated by Django 4.2.18 on 2025-04-15 03:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentservice', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='status',
            field=models.CharField(choices=[('available', 'Is Available'), ('inspection', 'Being Inspected'), ('in_circulation', 'In Circulation'), ('being_repaired', 'Being Repaired')], default='available', max_length=20),
        ),
    ]
