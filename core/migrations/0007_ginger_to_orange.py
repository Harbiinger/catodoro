from django.db import migrations


def ginger_to_orange(apps, schema_editor):
    Cat = apps.get_model('core', 'Cat')
    Cat.objects.filter(color='ginger').update(color='orange')


def orange_to_ginger(apps, schema_editor):
    Cat = apps.get_model('core', 'Cat')
    Cat.objects.filter(color='orange').update(color='ginger')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_cat_color_alter_player_coins'),
    ]

    operations = [
        migrations.RunPython(ginger_to_orange, orange_to_ginger),
    ]
