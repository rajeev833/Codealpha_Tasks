# Generated by Django 4.1.2 on 2023-01-15 13:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0002_alter_game_game_opponent'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamematrix',
            name='game_code',
            field=models.CharField(default='', max_length=6),
            preserve_default=False,
        ),
    ]
