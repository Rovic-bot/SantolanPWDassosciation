from django.db import migrations


def seed_labels(apps, schema_editor):
    status = apps.get_model('assistance', 'EligibilityStatus')
    for code, label in [('pending', 'Pending'), ('eligible', 'Eligible'), ('review', 'Review Needed'), ('ineligible', 'Not Eligible')]:
        status.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={'label': label})


class Migration(migrations.Migration):
    dependencies = [('assistance', '0001_initial')]
    operations = [migrations.RunPython(seed_labels, migrations.RunPython.noop)]
