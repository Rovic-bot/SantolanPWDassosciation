"""Synthetic evidence for disposable workflow tests; never production seed data."""
from tempfile import TemporaryDirectory
from django.test import override_settings
from django.db import transaction
from django.utils import timezone
from announcements.tests import image_upload
from .models import ProgramApplication, PhotoVerification
from .workflow import allocate_reference, store_photo


def private_media(test):
    directory = TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    override = override_settings(MEDIA_ROOT=directory.name)
    override.enable()
    test.addCleanup(override.disable)
    return directory


def verified_photo(application):
    application.member.refresh_from_db()
    if not application.current_photo_id:
        store_photo(application, image_upload(), [])
    PhotoVerification.objects.create(photo=application.current_photo, outcome='VERIFIED',
        reason='Synthetic manually reviewed test fixture.', reviewer_label='Synthetic Admin',
        member_version=application.member.version)
    application.status = 'PHOTO_VERIFIED'
    application.save(update_fields=['status'])


@transaction.atomic
def application_fixture(program, member):
    application = ProgramApplication.objects.create(program=program, member=member,
        public_reference=allocate_reference(program))
    verified_photo(application)
    return application


def close_non_ewaf_program(program, admin=None):
    assert not program.ewaf_applicable
    program.registration_closes_at = timezone.now() - timezone.timedelta(minutes=1)
    program.save(update_fields=['registration_closes_at'])


def approved_test_weights(user):
    """Approve fictional weights via the real current configuration service."""
    from scripts.durable_test_runner import require_disposable
    from ewaf import vault_services as vault
    from ewaf.dataset_methods import COMPOSITE
    from ewaf.test_composite_ses import proposal
    require_disposable()
    if not vault.active(COMPOSITE):
        for status in ('DRAFT', 'LOCKED'):
            vault.record_ses_weights(user=user, expected=vault.token(), proposal=proposal(),
                reason='SYNTHETIC test-only weights; no Association authorization.',
                status=status, method=COMPOSITE)
    return vault.active(COMPOSITE)


def current_program(user, **overrides):
    """A current published EWAF program using actual setup/publication guards."""
    from .tests import program_data
    from .services import save_program, change_publication
    approved_test_weights(user)
    program = save_program(user=user, data=program_data(ewaf_applicable=True, **overrides))
    from django.conf import settings
    if settings.PDAO_ENFORCEMENT_ENABLED:
        from .test_approved_terms import TermsHelpers
        helper = TermsHelpers()
        helper.program, helper.officer = program, user
        helper.reconcile()
    return change_publication(program.pk, user=user, version=program.version, action='published')


def historical_policy_authorization(program, user):
    """Seed pre-fixed-scoring authority for retained-method regression fixtures.

    Current authorization deliberately binds the November 10 fixed rules. Tests
    of retained dataset policies must start with historical records instead of
    authorizing a new fixed-rule program and then trying to convert its method.
    No scoring, binding, selection or publication guard is mocked by this helper.
    """
    from scripts.durable_test_runner import require_disposable
    from programs.services import record_log
    from ewaf.operational_models import OperationalConfiguration
    from ewaf.vault_policy import scoring_pending

    require_disposable()
    assert user.is_superuser and program.status == 'draft' and not program.policy_authorized_at
    configuration = OperationalConfiguration.objects.get(program=program)
    assert scoring_pending(configuration.policy) and not configuration.dataset_policy_id
    program.policy_authorized_at = timezone.now()
    program.policy_authorized_by = user
    program.updated_by = user
    program.version += 1
    program.save(update_fields=['policy_authorized_at', 'policy_authorized_by', 'updated_by', 'version'])
    record_log(program, 'policy_authorized', 'SYNTHETIC retained pre-November-10 policy authority.',
               user=user, changes={'policy_authorized_at': {'before': None, 'after': program.policy_authorized_at.isoformat()},
                                  'policy_authorized_by': {'before': None, 'after': user.pk}})
    return program


def scoring_application(program, user, control_number, *, income='1000.00'):
    """Fictional pre-close applicant with explicit provenance for ranking tests."""
    from unittest.mock import patch
    from members.tests import create_member
    from membership.services import record_event
    from scripts.durable_test_runner import require_disposable
    require_disposable()
    with patch('django.utils.timezone.now', return_value=program.registration_closes_at - timezone.timedelta(hours=1)):
        member = create_member(control_number)
        member.household_monthly_income = income
        member.employment_status = 'unemployed'
        member.household_members = 3
        member.registration_profile = {'four_ps_member': 'No'}
        member.save()
        intake = member.application
        intake.decided_by = intake.prpwd_verified_by = user
        intake.save()
        record_event(intake, 'prpwd_verified', 'Synthetic manual verification.', user=user)
        record_event(intake, 'approved', 'Synthetic membership approval.', user=user)
        application = application_fixture(program, member)
        application.source_snapshot = {'member_id': member.pk, 'member_version': member.version,
            'program_version': program.version, 'membership_verified_at': timezone.now().isoformat(),
            'policy_authorized_at': program.policy_authorized_at.isoformat()}
        application.save(update_fields=['source_snapshot'])
    return application
