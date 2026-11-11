from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.datastructures import MultiValueDict

from core.demo_seed import upload, photo_review, TEST
from members.tests import create_member
from members.models import Member, DisabilityType
from members.disability_catalog import NAMES
from membership.services import record_event
from programs.models import ProgramApplication, ProgramDocument
from programs.services import submit_application
from ewaf.evidence import source_context, digest
from ewaf.models import CriterionAssessment
from ewaf import operational_services as operational
from ewaf.weight_input import project
from . import access, sources
from .models import ApplicationCode, SocioeconomicReview
from .fixtures import create_program, configure, review_application as review


@override_settings(ROOT_URLCONF='program_intake.test_urls', PROGRAM_INTAKE_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=True)
class IntakeTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        setting = override_settings(MEDIA_ROOT=self.media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.actor = get_user_model().objects.create_superuser('intake_admin', password='fictional-only')
        from assistance.models import EligibilityStatus
        for code, label in [('pending', 'Pending'), ('eligible', 'Eligible'), ('review', 'Needs Information'), ('ineligible', 'Ineligible')]:
            EligibilityStatus.objects.get_or_create(code=code, defaults={'label': label})
        for name in NAMES:
            DisabilityType.objects.get_or_create(name=name)
        self.member = create_member('INTAKE-0001')
        self.member.disability_cause = 'congenital'
        self.member.disability_visibility = 'apparent'
        self.member.employment_status = 'employed'
        self.member.dependents = 1
        self.member.save()
        self.member.disability_types.set([self.member.disability_type_id])
        intake = self.member.application
        intake.prpwd_verified_by = intake.decided_by = self.actor
        intake.save()
        record_event(intake, 'prpwd_verified', TEST, user=self.actor)
        record_event(intake, 'approved', TEST, user=self.actor)
        self.program = create_program(self.actor)
        self.configuration = configure(self.program, self.actor)

    def data(self, **changes):
        return {'control_number': self.member.control_number, 'full_name': access.registered_name(self.member),
            'disability_types': self.member.disability_ids, 'disability_cause': self.member.disability_cause,
            'disability_visibility': self.member.disability_visibility, 'version': self.program.version, **changes}

    def grant(self, member=None, program=None):
        member, program = member or self.member, program or self.program
        return access.verify_member(program.pk, control_number=member.control_number,
            full_name=access.registered_name(member), disability_types=DisabilityType.objects.filter(pk__in=member.disability_ids),
            disability_cause=member.disability_cause, disability_visibility=member.disability_visibility, version=program.version)

    def submit(self, member=None, program=None, **kwargs):
        program = program or self.program
        required = program.configured_requirements.get(is_required=True)
        return submit_application(program.pk, grant=self.grant(member, program), data={'version': program.version},
            files=MultiValueDict({'calendar_photo': [upload(portrait=True)], f'requirement_{required.pk}': [upload('Observed need: 90 assessment units')]}), **kwargs)

    def prepare(self, app=None, value='90'):
        app = app or self.submit()
        photo_review(app, self.actor)
        review(app, self.actor)
        app.refresh_from_db()
        self.si(app, value=value)
        self.collect(app)
        return app

    def si(self, app, **changes):
        app.refresh_from_db()
        config = operational.latest_configuration(app.program)
        return sources.review_si(app.pk, user=self.actor, expected=sources.review_token(app, config),
            **{'state': 'VERIFIED', 'value': '90', 'observation_start': timezone.localdate(),
               'observation_end': timezone.localdate(), 'reason': TEST, 'confirmed': True, **changes})

    def collect(self, app):
        app.refresh_from_db()
        return sources.collect_sources(app.pk, user=self.actor, expected=digest(source_context(app)), reason=TEST, confirmed=True)

    def calculate(self):
        # Advance time in the disposable fixture; never mutate approved dates.
        with patch('django.utils.timezone.now', return_value=self.program.registration_closes_at + timedelta(seconds=1)):
            return operational.generate(self.program.pk, user=self.actor,
                expected=operational.context(self.program.pk, user=self.actor), reason=TEST, request_key=uuid4())

    def test_form_has_ten_shared_multiselect_choices_and_no_private_profile(self):
        response = self.client.get(reverse('programs:verify', args=[self.program.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['form'].fields['disability_types'].queryset), 10)
        self.assertContains(response, 'Association Control Number')
        self.assertContains(response, 'Full Name')
        self.assertNotContains(response, 'application_code')
        self.assertNotContains(response, 'one-time')
        self.assertNotContains(response, self.member.full_name)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('programs:verify', args=[self.program.pk]), self.data(full_name='Incorrect name')).status_code, 403)

    def test_successful_public_submission_has_documents_and_pending_status(self):
        response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data())
        self.assertRedirects(response, reverse('programs:apply', args=[self.program.pk]))
        requirement = self.program.configured_requirements.get(is_required=True)
        response = self.client.post(reverse('programs:apply', args=[self.program.pk]), {
            'version': self.program.version, 'calendar_photo': upload(portrait=True),
            f'requirement_{requirement.pk}': upload('Synthetic socioeconomic observation')})
        self.assertEqual(response.status_code, 302)
        app = ProgramApplication.objects.get()
        self.assertEqual(app.member, self.member)
        self.assertEqual(app.status, 'PENDING_PHOTO_VERIFICATION')
        self.assertTrue(app.public_reference)
        self.assertEqual(app.documents.count(), 1)
        self.assertEqual(len(app.requirements_snapshot), 2)
        self.assertEqual(Member.objects.count(), 1)
        self.assertFalse(CriterionAssessment.objects.exists())
        self.assertContains(self.client.get(response.url), app.public_reference)

    def test_private_match_failures_share_one_message(self):
        for changes in ({'control_number': 'UNKNOWN'}, {'disability_cause': 'acquired'},
                        {'disability_visibility': 'non_apparent'}, {'full_name': 'Incorrect name'},
                        {'disability_types': [DisabilityType.objects.get(name=NAMES[0]).pk]}):
            with self.subTest(changes=changes):
                response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(**changes))
                self.assertContains(response, escape(access.FAILED), status_code=response.status_code)
                self.assertNotContains(response, self.member.address, status_code=response.status_code)
                self.assertNotContains(response, self.member.contact_number, status_code=response.status_code)
                self.assertNotIn('program_verification', self.client.session)
        self.assertFalse(ProgramApplication.objects.exists())

    @override_settings(PROGRAM_VERIFICATION_MEMBER_LIMIT=2, PROGRAM_VERIFICATION_ADDRESS_LIMIT=3)
    def test_guessing_is_rate_limited_and_does_not_issue_grants(self):
        for index in range(3):
            response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(full_name='Incorrect name'))
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, escape(access.FAILED), status_code=429)
        self.assertIn('Retry-After', response)
        self.assertNotIn('program_verification', self.client.session)

    def test_session_grant_is_program_bound_expiring_and_tamper_checked(self):
        grant = self.grant()
        self.assertTrue(access.secure_grant(grant, self.program))
        self.assertFalse(ApplicationCode.objects.exists())
        second = create_program(self.actor, 'Another public program')
        self.assertFalse(access.secure_grant(grant, second))
        altered = {**grant, 'member': self.member.pk + 1}
        self.assertFalse(access.secure_grant(altered, self.program))
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(hours=1)):
            self.assertFalse(access.secure_grant(grant, self.program))

    def test_incomplete_or_old_code_grant_cannot_submit(self):
        grant = self.grant()
        grant.pop('match_signature')
        with self.assertRaises(ValidationError):
            submit_application(self.program.pk, grant=grant, data={}, files=MultiValueDict())
        grant.update(intake_code='old-code', intake_nonce='old-nonce')
        grant.pop('verification_method')
        self.assertFalse(access.secure_grant(grant, self.program))

    def test_case_whitespace_and_unicode_normalization_preserve_middle_and_suffix(self):
        self.member.first_name = 'José Luis'
        self.member.middle_name = 'Dela Cruz'
        self.member.last_name = 'Santos'
        self.member.suffix = 'Jr.'
        self.member.full_name = 'José Luis Dela Cruz Santos Jr.'
        self.member.save()
        response = self.client.post(reverse('programs:verify', args=[self.program.pk]),
            self.data(full_name='  JOS\u00c9   LUIS  DELA CRUZ SANTOS  JR.  '))
        self.assertEqual(response.status_code, 302)
        for name in ('Jos\u00e9 Luis Santos Jr.', 'Jos\u00e9 Luis Dela Cruz Santos', 'Jos\u00e9 Luis Other Santos Jr.'):
            response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(full_name=name))
            self.assertContains(response, escape(access.FAILED))
            self.assertNotIn('program_verification', self.client.session)

    def test_recorded_no_middle_name_and_custom_suffix(self):
        self.member.first_name, self.member.last_name = 'Fictional', 'Member'
        self.member.no_middle_name = True
        self.member.suffix, self.member.suffix_other = 'other', 'VII'
        self.member.save()
        response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(full_name='Fictional Member VII'))
        self.assertEqual(response.status_code, 302)

    def test_name_belonging_to_other_control_number_is_rejected(self):
        other = create_member('INTAKE-0002')
        other.full_name = 'Different Registered Person'
        other.save()
        response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(full_name=other.full_name))
        self.assertContains(response, escape(access.FAILED))
        self.assertNotIn('program_verification', self.client.session)

    def test_inactive_archived_and_unapproved_members_are_rejected(self):
        self.member.is_active = False
        self.member.save()
        with self.assertRaisesMessage(ValidationError, access.FAILED):
            self.grant()
        self.member.archived_at = timezone.now()
        self.member.save()
        with self.assertRaisesMessage(ValidationError, access.FAILED):
            self.grant()
        self.member.archived_at = None
        self.member.is_active = True
        self.member.save()
        self.member.application.status = 'pending'
        self.member.application.save()
        with self.assertRaisesMessage(ValidationError, access.FAILED):
            self.grant()

    def test_verified_match_does_not_update_membership_or_create_codes(self):
        before = Member.objects.values().get(pk=self.member.pk)
        self.grant()
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertFalse(ApplicationCode.objects.exists())
        self.assertEqual(self.client.get('/manage/program-intake/access/').status_code, 404)

    def test_changed_member_or_qualification_invalidates_grant(self):
        grant = self.grant()
        self.member.dependents += 1
        self.member.version += 1
        self.member.save()
        self.assertFalse(access.secure_grant(grant, self.program))
        grant = self.grant()
        self.member.disability_cause = 'acquired'
        self.member.save()
        self.assertFalse(access.secure_grant(grant, self.program))
        grant = self.grant()
        self.program.eligible_disability_types.set([DisabilityType.objects.get(name=NAMES[0])])
        self.assertFalse(access.secure_grant(grant, self.program))

    def test_missing_fields_and_invalid_choices_show_only_generic_failure(self):
        for changes in ({'full_name': ''}, {'disability_types': []}, {'disability_cause': 'invalid'}, {'version': 'bad'}):
            response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(**changes))
            self.assertContains(response, escape(access.FAILED))
            self.assertNotContains(response, 'This field is required.')
            self.assertNotContains(response, 'Select a valid choice.')
            self.assertNotIn('program_verification', self.client.session)

    def test_multiple_disabilities_match_by_identifier(self):
        extra = DisabilityType.objects.get(name=NAMES[0])
        self.member.disability_types.add(extra)
        grant = self.grant()
        self.assertTrue(access.secure_grant(grant, self.program))

    def test_public_multiple_disabilities_require_the_complete_recorded_set(self):
        self.member.disability_types.add(DisabilityType.objects.get(name=NAMES[0]))
        url = reverse('programs:verify', args=[self.program.pk])
        self.assertEqual(self.client.post(url, self.data()).status_code, 302)
        extra = DisabilityType.objects.exclude(pk__in=self.member.disability_ids).first()
        for ids in (self.member.disability_ids[:1], [*self.member.disability_ids, extra.pk]):
            response = self.client.post(url, self.data(disability_types=ids))
            self.assertContains(response, escape(access.FAILED))
            self.assertNotIn('program_verification', self.client.session)

    def test_matching_restriction_accepts_any_registered_type(self):
        restricted = create_program(self.actor, 'Matching program', restrictions=self.member.disability_ids, ewaf=False)
        self.assertEqual(self.submit(program=restricted).member, self.member)

    def test_nonmatching_program_restriction_rejects_verified_member(self):
        restricted = create_program(self.actor, 'Nonmatching program', restrictions=[DisabilityType.objects.get(name=NAMES[0]).pk], ewaf=False)
        with self.assertRaises(ValidationError):
            self.submit(program=restricted)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_missing_required_document_rejects_without_creating_application(self):
        with self.assertRaises(ValidationError):
            submit_application(self.program.pk, grant=self.grant(), data={'version': self.program.version},
                files=MultiValueDict({'calendar_photo': [upload(portrait=True)]}))
        self.assertFalse(ProgramApplication.objects.exists())

    def test_duplicate_returns_existing_application_and_preserves_original_evidence(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ProgramApplication.objects.count(), 1)
        self.assertEqual(ProgramDocument.objects.count(), 1)

    def test_closed_program_cannot_verify(self):
        with patch('django.utils.timezone.now', return_value=self.program.registration_closes_at + timedelta(seconds=1)):
            with self.assertRaisesMessage(ValidationError, access.FAILED):
                self.grant()

    def test_new_public_ewaf_application_requires_authorized_program_si_source(self):
        unconfigured = create_program(self.actor, 'Evidence policy pending')
        with self.assertRaisesMessage(ValidationError, access.FAILED):
            self.grant(program=unconfigured)

    def test_verified_nonmatching_qualification_explains_why_application_cannot_proceed(self):
        restricted = create_program(self.actor, 'Nonmatching public qualification',
            restrictions=[DisabilityType.objects.get(name=NAMES[0]).pk], ewaf=False)
        response = self.client.post(reverse('programs:verify', args=[restricted.pk]),
            self.data(version=restricted.version))
        self.assertContains(response, 'You cannot proceed with this application because')
        self.assertContains(response, 'target disability types')
        self.assertNotContains(response, escape(access.FAILED))
        self.assertNotIn('program_verification', self.client.session)

    @override_settings(PROGRAM_VERIFICATION_MEMBER_LIMIT=10, PROGRAM_VERIFICATION_ADDRESS_LIMIT=2)
    def test_ip_limit_cannot_be_evaded_by_rotating_control_numbers(self):
        for number in ('NOT-ONE', 'NOT-TWO', 'NOT-THREE'):
            response = self.client.post(reverse('programs:verify', args=[self.program.pk]), self.data(control_number=number))
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, escape(access.FAILED), status_code=429)

    def test_program_history_handles_retained_scalar_and_before_after_entries(self):
        from programs.services import record_log
        from programs.models import ProgramLog
        changes = {'code_id': 'historical-code-id', 'member_id': self.member.pk,
            'expires_at': '2026-10-21T12:00:00Z', 'name': {'before': 'Earlier name', 'after': '<script>unsafe</script>'},
            'requirements': {'before': {'label': 'Old'}, 'after': {'label': 'New', 'is_required': True}}}
        log = record_log(self.program, 'application_code_issued', 'Retained historical entry.', user=self.actor, changes=changes)
        before = ProgramLog.objects.values().get(pk=log.pk)
        self.client.force_login(self.actor)
        response = self.client.get(reverse('programs:manage_detail', args=[self.program.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'historical-code-id')
        self.assertContains(response, 'Earlier name')
        self.assertContains(response, '&lt;script&gt;unsafe&lt;/script&gt;')
        self.assertContains(response, 'Label: New; Required: Yes')
        self.assertEqual(ProgramLog.objects.values().get(pk=log.pk), before)
        for value in ('plain metadata', 3, None, ['a', 'b']):
            self.assertTrue(ProgramLog(changes=value).display_changes)

    def test_uploaded_si_is_not_verified_and_blocks_pool(self):
        app = self.submit()
        photo_review(app, self.actor)
        review(app, self.actor)
        with self.assertRaises(ValidationError):
            self.collect(app)
        with self.assertRaises(ValidationError):
            self.calculate()

    def test_onsite_sources_are_collected_and_score_trace_has_four_criteria(self):
        app = self.prepare()
        run = self.calculate()
        inputs = run.snapshot['eligible'][str(app.pk)]['inputs']
        self.assertEqual(inputs['ES']['value'], 'employed')
        self.assertEqual(inputs['ND']['value'], 1)
        self.assertEqual(inputs['PA']['value'], 0)
        self.assertEqual(inputs['SI']['value'], '90')
        traces = run.calculations[str(app.pk)]['traces']
        self.assertEqual({t['criterion'] for t in traces}, {'SI', 'ES', 'PA', 'ND'})
        self.assertFalse(CriterionAssessment.objects.filter(criterion='PR').exists())
        self.assertEqual(Decimal(run.calculations[str(app.pk)]['score_0_100']), Decimal('50.625'))
        self.assertFalse(run.snapshot['eligible'][str(app.pk)]['pr']['contributes_to_score'])

    def test_disputed_and_expired_si_block_recalculation(self):
        app = self.prepare()
        self.si(app, state='DISPUTED')
        with self.assertRaises(ValidationError):
            self.calculate()
        with self.assertRaises(ValidationError):
            self.si(app, observation_start=timezone.localdate() - timedelta(days=366), observation_end=timezone.localdate() - timedelta(days=366))

    def test_stale_review_token_is_rejected(self):
        app = self.prepare()
        token = sources.review_token(app, self.configuration)
        self.si(app, value='80')
        with self.assertRaises(ValidationError):
            sources.review_si(app.pk, user=self.actor, expected=token, state='VERIFIED', value='70',
                observation_start=timezone.localdate(), observation_end=timezone.localdate(), reason=TEST, confirmed=True)

    def test_corrected_si_appends_history_and_invalidates_old_run(self):
        app = self.prepare()
        first = self.calculate()
        retained = deepcopy(first.payload())
        self.si(app, value='20')
        with self.assertRaises(ValidationError):
            self.calculate()
        self.collect(app)
        second = self.calculate()
        self.assertEqual(second.previous_id, first.pk)
        self.assertNotEqual(second.calculations, first.calculations)
        first.refresh_from_db()
        self.assertEqual(first.payload(), retained)
        self.assertEqual(SocioeconomicReview.objects.count(), 2)
        with self.assertRaises(ValidationError):
            SocioeconomicReview.objects.all().delete()

    def test_out_of_bounds_si_is_not_clamped(self):
        app = self.submit()
        with self.assertRaises(ValidationError):
            self.si(app, value='101')

    def test_source_preview_and_review_are_permission_checked(self):
        app = self.submit()
        url = reverse('intake:sources', args=[app.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code, 200)
        document = app.documents.get()
        preview = reverse('programs:document', args=[self.program.pk, app.pk, document.pk])
        self.assertEqual(Client().get(preview).status_code, 302)

    def test_weight_revision_uses_ahp_and_preserves_previous_calculation(self):
        app = self.prepare()
        before = self.calculate()
        proposed = deepcopy(self.configuration.policy)
        judgments, _, provenance = project({'order': ['SI', 'ES', 'PA', 'ND'],
            'weights': {'SI': 7000, 'ES': 1000, 'PA': 1000, 'ND': 1000}})
        proposed['weight_input'] = provenance
        config = operational.record_configuration(self.program.pk, user=self.actor,
            expected=operational.configuration_token(self.program), proposed=proposed,
            judgments=judgments, status='LOCKED', reason=TEST, attested=True)
        after = self.calculate()
        self.assertEqual(config.revision, 2)
        self.assertEqual(after.previous_id, before.pk)
        self.assertAlmostEqual(Decimal(after.calculations[str(app.pk)]['score_0_100']), Decimal('74.25'), places=40)
        self.assertEqual(before.configuration_id, self.configuration.pk)

    def test_incomplete_pool_rejects_generation(self):
        app = self.prepare()
        # A later source correction makes a fully eligible application incomplete.
        self.si(app, state='REJECTED')
        with self.assertRaises(ValidationError):
            self.calculate()

    def test_confirmed_receipts_only_and_voids_change_pa_source(self):
        from assistance.services import decide_assistance, void_release
        from core.demo_seed import receive
        now = timezone.now()
        with patch('django.utils.timezone.now', return_value=now - timedelta(days=5)):
            historical = create_program(self.actor, 'Actual receipt fixture', ewaf=False, closes=now - timedelta(days=1))
            historical_app = self.submit(program=historical)
            photo_review(historical_app, self.actor)
            review(historical_app, self.actor)
        historical_app.refresh_from_db()
        decide_assistance(historical_app.pk, user=self.actor, data={'version': historical_app.version,
            'decision': 'approved', 'notes': TEST, 'confirm': True})
        app = self.prepare()
        self.assertEqual(CriterionAssessment.objects.filter(application=app, criterion='PA').first().value, 0)
        receipt = receive(historical_app, self.actor, 'FICTIONAL-RECEIPT')
        with self.assertRaises(ValidationError):
            self.calculate()
        self.collect(app)
        self.assertEqual(CriterionAssessment.objects.filter(application=app, criterion='PA').first().value, 1)
        historical_app.refresh_from_db()
        void_release(historical_app.pk, receipt.pk, user=self.actor, data={'version': historical_app.version,
            'notes': TEST + ' Correct incorrect fictional receipt.', 'confirm': True})
        with self.assertRaises(ValidationError):
            self.calculate()
        self.collect(app)
        self.assertEqual(CriterionAssessment.objects.filter(application=app, criterion='PA').first().value, 0)
        self.calculate()

    def test_member_source_correction_invalidates_verified_inputs(self):
        from members.services import update_member
        from membership.forms import PROFILE_FIELDS
        app = self.prepare()
        old = self.calculate()
        data = {name: getattr(self.member, name) for name in PROFILE_FIELDS}
        data.update(disability_types=self.member.disability_ids, employment_status='retired', dependents='4')
        update_member(self.member.pk, user=self.actor, version=self.member.version, data=data, notes=TEST)
        with self.assertRaises(ValidationError):
            self.calculate()
        self.assertEqual(old.snapshot['eligible'][str(app.pk)]['inputs']['ES']['value'], 'employed')

    def test_unmapped_employment_is_not_fabricated(self):
        self.member.employment_status = ''
        self.member.save()
        app = self.submit()
        photo_review(app, self.actor)
        review(app, self.actor)
        self.si(app)
        with self.assertRaises(ValidationError):
            self.collect(app)
        self.assertFalse(CriterionAssessment.objects.filter(application=app).exists())

    def test_selection_capacity_receipt_and_history_remain_separate(self):
        from core.demo_seed import receive
        from assistance.models import AssistanceRelease
        app = self.prepare()
        run = self.calculate()
        with patch('django.utils.timezone.now', return_value=self.program.registration_closes_at + timedelta(seconds=1)):
            decision = operational.record_decision(self.program.pk, user=self.actor, run_id=run.pk,
                application_id=app.pk, expected_revision=0, outcome='SELECTED', reason=TEST)
            self.assertFalse(AssistanceRelease.objects.exists())
            receipt = receive(app, self.actor, 'FICTIONAL-SELECTED-RECEIPT')
            self.assertIsNone(receipt.voided_at)
            self.assertEqual(decision.outcome, 'SELECTED')

    def test_source_policy_changes_are_versioned_and_preserve_ahp(self):
        from .policy import authorize_sources
        app = self.prepare()
        original = self.calculate()
        config = authorize_sources(self.program.pk, user=self.actor,
            expected=operational.configuration_token(self.program),
            requirement=self.program.configured_requirements.get(is_required=True),
            measure='Fictional separately authorized measurement', unit='fictional units', lower=Decimal('0'), upper=Decimal('200'),
            direction='inverse', observation_period='Observed within the previous 30 days', freshness_days=30,
            authority_reference=TEST, reason=TEST, confirmed=True)
        self.assertEqual(config.judgments, self.configuration.judgments)
        self.assertEqual(config.revision, 2)
        with self.assertRaises(ValidationError):
            self.calculate()
        original.refresh_from_db()
        original.clean()
