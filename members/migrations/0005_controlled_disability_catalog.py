from django.db import migrations


def add_catalog(apps, schema_editor):
    # Add only. Do not rename, merge, reactivate or remove older classifications.
    model = apps.get_model('members', 'DisabilityType')
    for name in (
        'Cancer (RA 11215)', 'Deaf or Hard of Hearing', 'Intellectual Disability',
        'Learning Disability', 'Mental Disability', 'Physical Disability (Orthopedic)',
        'Psychosocial Disability', 'Rare Disease (RA 10747)',
        'Speech and Language Impairment', 'Visual Disability',
    ):
        model.objects.using(schema_editor.connection.alias).get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [('members', '0004_onsite_profile_capture')]
    operations = [migrations.RunPython(add_catalog, migrations.RunPython.noop)]
