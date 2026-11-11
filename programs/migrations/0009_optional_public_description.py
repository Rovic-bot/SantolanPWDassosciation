from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('programs', '0008_incomplete_program_drafts')]

    operations = [
        migrations.RemoveConstraint(model_name='program', name='public_program_complete'),
        migrations.AddConstraint(
            model_name='program',
            constraint=models.CheckConstraint(
                condition=~models.Q(status__in=['published', 'cancelled']) | (
                    models.Q(registration_opens_at__isnull=False, registration_closes_at__isnull=False)
                    & ~models.Q(name='') & ~models.Q(assistance_type='')),
                name='public_program_complete',
            ),
        ),
    ]
