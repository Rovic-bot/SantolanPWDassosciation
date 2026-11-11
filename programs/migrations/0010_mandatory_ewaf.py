from django.db import migrations, models
import django.core.validators


def adopt(apps, schema_editor):
    from programs.mandatory_ewaf import adopt_existing_programs
    adopt_existing_programs(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [('programs', '0009_optional_public_description'),
                    ('announcements', '0007_certificate_email_provider')]

    operations = [
        migrations.AlterField(model_name='program', name='ewaf_applicable',
            field=models.BooleanField(default=True, editable=False)),
        migrations.AlterField(model_name='program', name='slots',
            field=models.PositiveIntegerField(null=True, validators=[django.core.validators.MinValueValidator(1)])),
        migrations.AlterField(model_name='program', name='eligible_disability_types',
            field=models.ManyToManyField(related_name='programs', to='members.disabilitytype')),
        migrations.RunPython(adopt, reverse_code=None),
    ]
