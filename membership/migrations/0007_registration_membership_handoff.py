"""Only the reviewed pending-intake link/state extension; no member backfill.

Reverse is deliberately refused while any link exists. Disable handoff instead
of removing provenance or deleting Members to force a downgrade.
"""
from django.db import migrations, models


def require_unlinked_reverse(apps, schema_editor):
    Intake = apps.get_model('membership', 'RegistrationIntake')
    if Intake.objects.using(schema_editor.connection.alias).filter(membership_application__isnull=False).exists():
        raise RuntimeError('Registration handoff links exist. Keep provenance and disable handoff; reversal requires a separately reviewed recovery plan.')


class Migration(migrations.Migration):
    dependencies = [('membership', '0006_association_pending_intake')]
    operations = [
        migrations.RemoveConstraint(model_name='registrationintake', name='reg_handoff_unavailable'),
        migrations.RemoveConstraint(model_name='registrationintake', name='reg_pending_states'),
        migrations.AlterField(model_name='registrationintake', name='state',
            field=models.CharField(max_length=32, default='received', choices=[
                ('received', 'Received'), ('under_review', 'Under review'),
                ('needs_information', 'Needs information'), ('ready_for_onsite', 'Ready for onsite verification'),
                ('onsite_review', 'Onsite findings recorded'), ('membership_review', 'Membership review')])),
        migrations.AddConstraint(model_name='registrationintake', constraint=models.CheckConstraint(
            condition=models.Q(state__in=['received', 'under_review', 'needs_information',
                'ready_for_onsite', 'onsite_review', 'membership_review']), name='reg_pending_states')),
        migrations.AddConstraint(model_name='registrationintake', constraint=models.CheckConstraint(
            condition=(models.Q(membership_application__isnull=False, state='membership_review') |
                (models.Q(membership_application__isnull=True) & ~models.Q(state='membership_review'))),
            name='reg_handoff_link_state')),
        # Last forward operation runs FIRST during reversal, before any DDL.
        migrations.RunPython(migrations.RunPython.noop, require_unlinked_reverse),
    ]
