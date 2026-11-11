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
