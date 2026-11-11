"""G06-B1B.1; synthetic data only, in a disposable native MySQL database."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.forms import modelform_factory
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from documents.models import DocumentType
from events.forms import EventForm
from events.models import Event
from events.services import save_event, change_publication as event_publication
from events.tests import create_event, event_data
from members.models import DisabilityType
from members.tests import create_member
from membership.tests import grant as permissions
from .approval_policy import require_binding
from .approval_services import record_pdao_approval
from .binding_services import VIEW, WRITE, capture_terms, bind_approval, preflight
from .forms import ProgramForm, RequirementForm
from .models import (Program, ProgramRequirement, ProgramTermsRevision, ProgramApprovalBinding,
                     ProgramApprovalControl, ProgramLog, PDAOApprovalRecord, ProgramApplication)
from .services import save_program, save_requirement, change_publication, require_open, verify_member, submit_application
from .terms import PROGRAM_FIELDS, snapshot_terms, terms_digest
from .test_pdao_approval import approval_data
from .tests import create_program, program_data, verification
from .testsupport import private_media


class TermsHelpers:
    def setup_terms(self, *, draft=False):
        self.officer = get_user_model().objects.create_superuser('synthetic_terms_officer')
        self.program = create_program(budget=Decimal('98765.43'), amount=Decimal('123.45'))
        if draft:
            Program.objects.filter(pk=self.program.pk).update(status='draft', published_at=None, policy_authorized_at=None)
            self.program.refresh_from_db()

    def record(self, **changes):
        latest = self.program.pdao_approval_records.first()
        return record_pdao_approval(self.program.pk, user=self.officer, data=approval_data(
            expected_version=latest.version if latest else 0, expected_program_version=self.program.version, **changes))

    def capture(self, **changes):
        control = ProgramApprovalControl.objects.filter(program=self.program).first()
        values = dict(user=self.officer, version=control.version if control else 0,
                      program_version=self.program.version, digest=terms_digest(snapshot_terms(self.program)),
                      reason='Synthetic complete terms review.', confirmed=True)
        return capture_terms(self.program.pk, **{**values, **changes})

    def bind(self, revision, approval, **changes):
        control = ProgramApprovalControl.objects.get(program=self.program)
        values = dict(user=self.officer, version=control.version, program_version=self.program.version,
                      revision_id=revision.pk, approval_id=approval.pk,
                      approval_version=self.program.pdao_approval_records.first().version,
                      reason='Synthetic officer confirms physical approval covers displayed terms.', confirmed=True)
        return bind_approval(self.program.pk, **{**values, **changes})

    def reconcile(self, **approval_changes):
        revision = self.capture()
        approval = self.record(**approval_changes)
        return self.bind(revision, approval)

    def edit_data(self, **changes):
        data = {key: getattr(self.program, key) for key in PROGRAM_FIELDS}
        return {**data, 'eligible_disability_types': list(self.program.eligible_disability_types.values_list('pk', flat=True)),
                'version': self.program.version, 'notes': 'Synthetic configuration change.', **changes}


class ApprovedTermsTests(TermsHelpers, TestCase):
    def setUp(self):
        self.setup_terms()

    def test_canonical_snapshot_is_deterministic_complete_and_excludes_private_data_and_budget(self):
        document = DocumentType.objects.create(name='Synthetic reference', description='Synthetic historical definition')
        req = ProgramRequirement.objects.create(program=self.program, label='Synthetic proof', kind='document',
            instructions='Synthetic instructions', is_active=False, is_required=False, position=3, reusable_document_type=document)
        event = create_event(application_program=self.program)
        snapshot = snapshot_terms(self.program)
        self.assertEqual(terms_digest(snapshot), terms_digest(json.loads(json.dumps(snapshot, sort_keys=True))))
        self.assertEqual(terms_digest(snapshot), terms_digest(snapshot_terms(Program.objects.get(pk=self.program.pk))))
        self.assertEqual(set(snapshot['program']), set(PROGRAM_FIELDS))
        self.assertEqual(snapshot['program']['amount'], '123.45')
        self.assertTrue(snapshot['program']['registration_opens_at'].endswith('+00:00'))
        self.assertEqual(snapshot['event']['id'], str(event.pk))
        self.assertEqual(snapshot['requirements'], [{'id': req.pk, 'label': req.label, 'kind': 'document',
            'instructions': req.instructions, 'is_required': False, 'is_active': False, 'position': 3,
            'document_type': {'id': document.pk, 'name': document.name, 'description': document.description}}])
        self.assertEqual(snapshot['disability_qualifications'][0]['is_active'], True)
        for excluded in ('budget', 'approved_budget', 'member', 'signatory', 'file', 'control_number'):
            self.assertNotIn('"' + excluded + '"', json.dumps(snapshot))

    def test_revision_and_binding_are_immutable_and_have_matching_audits(self):
        binding = self.reconcile()
        for artifact, action in ((binding, 'approval_bound'), (binding.revision, 'terms_recorded')):
            self.assertEqual(artifact.audit_entry.action, action)
            self.assertEqual(artifact.audit_entry.actor, self.officer)
            self.assertEqual(artifact.audit_entry.program, self.program)
            with self.assertRaises(ValidationError):
                artifact.save()
            with self.assertRaises(ValidationError):
                artifact.delete()
            with self.assertRaises(ValidationError):
                type(artifact).objects.filter(pk=artifact.pk).update(reason='Forged overwrite')
            with self.assertRaises(ValidationError):
                type(artifact).objects.all().delete()

    def test_model_validation_rejects_mismatched_audit_and_budget_snapshot(self):
        revision = self.capture()
        other = create_program()
        revision.audit_entry = ProgramLog.objects.create(program=other, actor=self.officer,
            action='terms_recorded', notes='Synthetic wrong-program audit')
        with self.assertRaises(ValidationError):
            revision.full_clean()
        revision.refresh_from_db()
        revision.snapshot['program']['budget'] = '1.00'
        revision.digest = terms_digest(revision.snapshot)
        with self.assertRaises(ValidationError):
            revision.full_clean()

    def test_audit_failure_rolls_back_revision_binding_and_control(self):
        with patch('programs.binding_services.record_log', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.capture()
        self.assertFalse(ProgramApprovalControl.objects.exists())
        self.assertFalse(ProgramTermsRevision.objects.exists())
        revision, approval = self.capture(), self.record()
        before = ProgramApprovalControl.objects.values().get()
        with patch('programs.models.ProgramApprovalBinding.save', side_effect=RuntimeError('Synthetic insert failure')):
            with self.assertRaises(RuntimeError):
                self.bind(revision, approval)
        self.assertEqual(ProgramApprovalControl.objects.values().get(), before)
        self.assertFalse(ProgramLog.objects.filter(action='approval_bound').exists())

    def test_stale_missing_confirmation_and_cross_program_requests_fail(self):
        revision, approval = self.capture(), self.record()
        other = create_program()
        other_approval = record_pdao_approval(other.pk, user=self.officer, data=approval_data())
        for forged in ({'version': 0}, {'program_version': 99}, {'confirmed': False}, {'reason': '  '},
                       {'approval_version': 99}, {'approval_id': other_approval.pk}, {'revision_id': 999999}):
            with self.subTest(forged=forged), self.assertRaises(ValidationError):
                self.bind(revision, approval, **forged)
        with self.assertRaises(ValidationError):
            self.capture(digest='0' * 64)
        self.assertFalse(ProgramApprovalBinding.objects.exists())

    def test_newer_approval_does_not_change_active_binding(self):
        bound = self.reconcile()
        control = ProgramApprovalControl.objects.values().get()
        newer = self.record()
        self.assertEqual(ProgramApprovalControl.objects.values().get(), control)
        with self.assertRaises(ValidationError):
            self.bind(bound.revision, newer, approval_version=1)
        replacement = self.bind(bound.revision, newer)
        self.assertEqual(ProgramApprovalBinding.objects.count(), 2)
        self.assertEqual(ProgramApprovalControl.objects.get().active_binding, replacement)
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, 0)

    def test_legacy_binding_is_explicit_and_unknown_metadata_stays_unknown(self):
        before = Program.objects.filter(pk=self.program.pk).values().get()
        bound = self.reconcile(kind='legacy', approval_date='', signatory='')
        self.assertEqual(bound.approval_record.kind, 'legacy')
        self.assertIsNone(bound.approval_record.approval_date)
        self.assertEqual(bound.approval_record.signatory, '')
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            require_open(Program.objects.get(pk=self.program.pk))

    def test_previous_publication_or_approval_record_never_implicitly_authorizes(self):
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            for step in (lambda: None, self.record, self.capture):
                step()
                with self.assertRaises(ValidationError):
                    require_open(Program.objects.get(pk=self.program.pk))
                self.assertFalse(Program.objects.accepting_applications().exists())
        self.assertFalse(ProgramApprovalBinding.objects.exists())

    @override_settings(PDAO_ENFORCEMENT_ENABLED=True)
    def test_protected_fields_and_disability_set_are_frozen_before_any_application(self):
        changes = {key: ('Changed synthetic text' if isinstance(getattr(self.program, key), str) else None) for key in PROGRAM_FIELDS}
        changes.update(slots=3, amount='999.00', ewaf_applicable=True,
                       registration_opens_at=self.program.registration_opens_at - timedelta(hours=1),
                       registration_closes_at=self.program.registration_closes_at + timedelta(hours=1),
                       starts_at=timezone.now() + timedelta(days=2), ends_at=timezone.now() + timedelta(days=3),
                       resubmission_closes_at=timezone.now() + timedelta(days=4), eligible_disability_types=[])
        before = Program.objects.filter(pk=self.program.pk).values().get()
        for field, value in changes.items():
            with self.subTest(field=field):
                form = ProgramForm(self.edit_data(**{field: value}), instance=Program.objects.get(pk=self.program.pk))
                if field in ('amount', 'benefit'):
                    self.assertTrue(form.is_valid(), form.errors)
                    save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(**{field: value}))
                    self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)
                    continue
                self.assertFalse(form.is_valid())
                self.assertIn('protected', str(form.errors))
                with self.assertRaises(ValidationError):
                    save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(**{field: value}))
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)

    def test_requirements_and_reference_model_forms_bulk_updates_and_deletion_are_guarded(self):
        ref = self.program.eligible_disability_types.get()
        document = DocumentType.objects.create(name='Synthetic protected type')
        req = ProgramRequirement.objects.create(program=self.program, label='Proof', kind='document', reusable_document_type=document)
        data = {'version': 0, 'notes': 'Synthetic change', 'label': 'Forged new proof', 'kind': 'text', 'position': 0}
        self.assertFalse(RequirementForm(data, instance=req).is_valid())
        with self.assertRaises(ValidationError):
            save_requirement(self.program.pk, user=self.officer, data=data)
        for instance, field, value in ((ref, 'is_active', False), (ref, 'name', 'Replaced meaning'),
                                       (document, 'description', 'Replaced meaning'), (document, 'name', 'Replaced type')):
            with self.subTest(field=field):
                form_class = modelform_factory(type(instance), fields=(field,))
                self.assertFalse(form_class({field: value}, instance=instance).is_valid())
                setattr(instance, field, value)
                with self.assertRaises(ValidationError):
                    instance.save()
                with self.assertRaises(ValidationError):
                    type(instance).objects.filter(pk=instance.pk).update(**{field: value})
                with self.assertRaises(ValidationError):
                    type(instance).objects.bulk_update([instance], [field])
                with self.assertRaises(ValidationError):
                    instance.delete()
                instance.refresh_from_db()
        forged = DisabilityType(pk=ref.pk, name='Synthetic forged replacement', is_active=True)
        with self.assertRaises(ValidationError):
            forged.save()

    def test_event_link_schedule_and_description_edits_are_blocked_but_withdrawal_remains(self):
        event = create_event(application_program=self.program)
        for changes in ({'starts_at': event.starts_at + timedelta(minutes=1)}, {'description': 'Changed terms'},
                        {'application_program': ''}, {'capacity': 50}):
            with self.subTest(changes=changes):
                data = event_data(application_program=self.program.pk, **{k: v for k, v in changes.items() if k != 'application_program'})
                data.update(changes)
                with self.assertRaises(ValidationError):
                    save_event(pk=event.pk, user=self.officer, data=data, files=MultiValueDict())
        withdrawn = event_publication(event.pk, user=self.officer, version=0, action='draft', notes='Synthetic withdrawal')
        self.assertEqual(withdrawn.status, 'draft')
        self.assertFalse(Program.objects.get(pk=self.program.pk).registration_available)

    def test_adding_event_link_to_protected_program_is_rejected(self):
        data = event_data(application_program=self.program.pk)
        self.assertFalse(EventForm(data, user=self.officer).is_valid())
        with self.assertRaises(ValidationError):
            save_event(user=self.officer, data=data, files=MultiValueDict())

    def test_each_permission_and_forged_http_requests_csrf_uploads(self):
        revision, approval = self.capture(), self.record()
        url = reverse('programs:terms_review', args=[self.program.pk])
        for missing in ('accounts.access_dashboard', *WRITE):
            user = get_user_model().objects.create_user('synthetic_' + missing, is_staff=True)
            permissions(user, *(p for p in ('accounts.access_dashboard', *WRITE) if p != missing))
            with self.subTest(permission=missing), self.assertRaises(PermissionDenied):
                self.bind(revision, approval, user=user)
            self.client.force_login(user)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.bind(revision, approval, user=AnonymousUser())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.officer)
        self.assertEqual(csrf.post(url, {}).status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertContains(self.client.post(url, {'letter': image_upload()}), 'Uploads are not accepted.')
        self.assertFalse(ProgramApprovalBinding.objects.exists())

    def test_readiness_history_and_public_privacy(self):
        bound = self.reconcile()
        self.client.force_login(self.officer)
        readiness = self.client.get(reverse('programs:pdao_readiness'))
        self.assertEqual(readiness.status_code, 200)
        self.assertIn('no-store', readiness['Cache-Control'])
        response = self.client.get(reverse('programs:terms_review', args=[self.program.pk]))
        self.assertContains(response, 'Philippine time')
        self.assertContains(response, 'for="id_confirmed"')
        self.assertNotContains(response, 'name="budget"')
        historical = self.client.get(reverse('programs:terms_revision', args=[self.program.pk, bound.revision_id]))
        self.assertContains(historical, 'Immutable recorded terms')
        self.assertNotContains(historical, 'name="confirmed"')
        other = create_program()
        self.assertEqual(self.client.get(reverse('programs:terms_revision', args=[other.pk, bound.revision_id])).status_code, 404)
        public = self.client.get(reverse('programs:detail', args=[self.program.pk]))
        self.assertNotContains(public, 'Synthetic PDAO signatory')
        self.assertNotContains(public, 'approval_bound')

    def test_http_capture_and_bind_ignore_forged_business_fields_and_require_confirmation(self):
        self.client.force_login(self.officer)
        url = reverse('programs:terms_review', args=[self.program.pk])
        approval = self.record()
        before = Program.objects.filter(pk=self.program.pk).values().get()
        payload = {'action': 'capture', 'version': 0, 'program_version': 0,
                   'digest': terms_digest(snapshot_terms(self.program)), 'approval_version': approval.version,
                   'reason': 'Synthetic terms reviewed', 'budget': '0', 'status': 'draft', 'slots': 900}
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        self.assertFalse(ProgramTermsRevision.objects.exists())
        self.assertEqual(self.client.post(url, {**payload, 'confirmed': True}).status_code, 302)
        revision = ProgramTermsRevision.objects.get()
        payload.update(action='bind', version=1, revision_id=revision.pk, approval_id=999999, confirmed=True)
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        self.assertFalse(ProgramApprovalBinding.objects.exists())
        payload['approval_id'] = approval.pk
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(ProgramApprovalBinding.objects.count(), 1)
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)

    def test_reconciled_legacy_cannot_bind_later_changed_terms_or_become_official_implicitly(self):
        bound = self.reconcile(kind='legacy', approval_date='', signatory='')
        self.record()
        self.assertEqual(ProgramApprovalControl.objects.get().active_binding.approval_record.kind, 'legacy')
        Program.objects.filter(pk=self.program.pk).update(slots=99)  # Synthetic out-of-band drift.
        self.program.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.capture()
        with self.assertRaises(ValidationError):
            self.bind(bound.revision, bound.approval_record)

    def test_enabled_public_unavailable_message_hides_internal_approval_details(self):
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            self.record()
            response = self.client.get(reverse('programs:detail', args=[self.program.pk]))
            self.assertContains(response, 'Applications unavailable')
            self.assertNotContains(response, 'Apply for this program')
            self.assertNotContains(response, 'Synthetic PDAO signatory')
            with self.assertRaisesMessage(ValidationError, 'Applications are currently unavailable'):
                require_open(self.program)

    def test_preflight_is_read_only_and_refuses_missing_or_drifted_reconciliation(self):
        self.assertFalse(preflight()['ready'])
        self.assertFalse(ProgramApprovalControl.objects.exists())
        with self.assertRaises(CommandError):
            call_command('pdao_cutover_preflight', verbosity=0)
        self.reconcile()
        before = list(ProgramApprovalControl.objects.values())
        self.assertEqual(preflight(), {'operating': 1, 'unresolved': 0, 'drift': 0, 'ready': True})
        self.assertEqual(list(ProgramApprovalControl.objects.values()), before)
        # Deliberately simulate privileged database drift, not an authorized edit.
        Program.objects.filter(pk=self.program.pk).update(slots=77)
        self.assertEqual(preflight()['drift'], 1)
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True), self.assertRaises(ValidationError):
            require_binding(Program.objects.get(pk=self.program.pk))

    def test_disabled_mode_preserves_operating_program_and_budget_without_inferred_approval(self):
        before = Program.objects.filter(pk=self.program.pk).values().get()
        with override_settings(PDAO_ENFORCEMENT_ENABLED=False):
            require_open(self.program)
            self.assertTrue(Program.objects.accepting_applications().exists())
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramApprovalBinding.objects.exists())
        self.reconcile()
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)
        save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(budget='0'))
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)

    def test_enabled_public_boundaries_labels_internal_policy_and_event_parity(self):
        self.reconcile()
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            for at, available, status in ((self.program.registration_opens_at - timedelta(microseconds=1), False, 'upcoming'),
                (self.program.registration_opens_at, True, 'open'),
                (self.program.registration_closes_at - timedelta(microseconds=1), True, 'open'),
                (self.program.registration_closes_at, False, 'ended')):
                # Publication predates the entire tested application window.
                Program.objects.filter(pk=self.program.pk).update(published_at=self.program.registration_opens_at - timedelta(days=1))
                with patch('django.utils.timezone.now', return_value=at):
                    item = Program.objects.get(pk=self.program.pk)
                    self.assertEqual(item.registration_available, available)
                    with self.assertNumQueries(1):
                        self.assertEqual(Program.objects.accepting_applications(at=at).exists(), available)
                    self.assertEqual(Program.objects.with_public_application_status(at=at).get().public_application_status, status)
            for status in ('cancelled', 'draft', 'archived'):
                Program.objects.filter(pk=self.program.pk).update(status=status)
                self.assertFalse(Program.objects.accepting_applications().exists())
            Program.objects.filter(pk=self.program.pk).update(status='published', policy_authorized_at=None)
            self.assertFalse(Program.objects.accepting_applications().exists())

    def test_event_availability_parity_in_both_flag_modes(self):
        # Link is part of the terms before reconciliation.
        event = create_event(application_program=self.program)
        self.reconcile()
        for enabled in (False, True):
            with override_settings(PDAO_ENFORCEMENT_ENABLED=enabled):
                for status in ('published', 'draft', 'cancelled', 'archived'):
                    Event.objects.filter(pk=event.pk).update(status=status)
                    item = Program.objects.get(pk=self.program.pk)
                    self.assertEqual(item.registration_available, status == 'published')
                    self.assertEqual(Program.objects.accepting_applications().exists(), status == 'published')
                    if status == 'published':
                        require_open(item)
                    else:
                        with self.assertRaises(ValidationError):
                            require_open(item)

    def test_stale_verification_rejected_after_explicit_binding_replacement(self):
        private_media(self)
        binding = self.reconcile()
        member = create_member('SYNTHETIC-BINDING-GRANT')
        member.refresh_from_db()
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            verified = verify_member(self.program.pk, **verification(member, self.program))
            self.bind(binding.revision, self.record())
            with self.assertRaises(ValidationError):
                submit_application(self.program.pk, grant=verified, data={'version': 0}, files=MultiValueDict({'calendar_photo': [image_upload()]}))
            self.assertFalse(ProgramApplication.objects.exists())
            verified = verify_member(self.program.pk, **verification(member, self.program))
            app = submit_application(self.program.pk, grant=verified, data={'version': 0}, files=MultiValueDict({'calendar_photo': [image_upload()]}))
            self.assertEqual(app.source_snapshot['approval_binding'], ProgramApprovalControl.objects.get().active_binding_id)

    def test_binding_preserves_historical_application_eligibility_results_and_release(self):
        from announcements.models import Announcement, ProgramResultRevision
        from announcements.results import prepare_results, results_current
        from announcements.services import change_publication as publish_results
        from assistance.models import AssistanceCase, AssistanceRelease
        from assistance.services import review_eligibility, decide_assistance, record_release
        from assistance.tests import create_application, review_data, decision_data, release_data, seed_statuses
        from .testsupport import close_non_ewaf_program
        private_media(self)
        seed_statuses()
        app = create_application(program=self.program)
        review_eligibility(app.pk, user=self.officer, data=review_data(app))
        close_non_ewaf_program(self.program)
        decide_assistance(app.pk, user=self.officer, data=decision_data(app))
        release = record_release(app.pk, user=self.officer, data=release_data(app))
        announcement = prepare_results(self.program.pk, user=self.officer, version=0, reason='Synthetic published result')
        announcement = publish_results(announcement.pk, user=self.officer, version=announcement.version, action='published')
        preserved = [(model, list(model.objects.values())) for model in
                     (Program, ProgramApplication, AssistanceCase, AssistanceRelease, Announcement, ProgramResultRevision)]
        history = list(ProgramLog.objects.values())
        self.program.refresh_from_db()
        self.reconcile()
        for model, before in preserved:
            self.assertEqual(list(model.objects.values()), before, model._meta.label)
        for log in history:
            self.assertEqual(ProgramLog.objects.filter(pk=log['id']).values().get(), log)
        self.assertTrue(results_current(announcement))
        self.assertTrue(AssistanceRelease.objects.filter(pk=release.pk).exists())

    def test_readiness_pagination_and_view_only_permissions(self):
        for index in range(21):
            create_program(name=f'Synthetic pagination program {index:02}')
        viewer = get_user_model().objects.create_user('synthetic_terms_viewer', is_staff=True)
        permissions(viewer, 'accounts.access_dashboard', *VIEW)
        self.client.force_login(viewer)
        response = self.client.get(reverse('programs:pdao_readiness'))
        self.assertEqual(len(response.context['page_obj']), 20)
        second = self.client.get(reverse('programs:pdao_readiness'), {'page': 2})
        self.assertEqual(len(second.context['page_obj']), 2)
        response = self.client.get(reverse('programs:terms_review', args=[self.program.pk]))
        self.assertNotContains(response, 'name="confirmed"')
        self.assertEqual(self.client.post(reverse('programs:terms_review', args=[self.program.pk]), {}).status_code, 403)

    def test_enabled_mode_rejects_corrupt_control_and_cross_program_pointer(self):
        binding = self.reconcile()
        other = create_program()
        ProgramApprovalControl.objects.create(program=other, current_revision=binding.revision,
                                            current_digest=binding.revision.digest, active_binding=binding, version=1)
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            self.assertFalse(Program.objects.accepting_applications().filter(pk=other.pk).exists())
            with self.assertRaises(ValidationError):
                require_open(Program.objects.get(pk=other.pk))
            ProgramApprovalControl.objects.filter(program=self.program).update(current_digest='0' * 64)
            self.assertFalse(Program.objects.accepting_applications().filter(pk=self.program.pk).exists())
            with self.assertRaises(ValidationError):
                require_open(Program.objects.get(pk=self.program.pk))


class DraftApprovedTermsTests(TermsHelpers, TestCase):
    def setUp(self):
        self.setup_terms(draft=True)

    def test_official_approval_can_bind_draft_and_is_required_for_first_publication(self):
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            with self.assertRaises(ValidationError):
                change_publication(self.program.pk, user=self.officer, version=0, action='published', notes='Synthetic publication')
            self.reconcile()
            self.program.refresh_from_db()
            self.assertEqual(self.program.status, 'draft')
            self.assertEqual(self.program.version, 0)
            published = change_publication(self.program.pk, user=self.officer, version=0, action='published', notes='Synthetic publication')
            self.assertTrue(published.registration_available)

    def test_unapproved_draft_initial_configuration_is_editable_but_recorded_approval_freezes_it(self):
        self.program = save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(slots=5))
        save_requirement(self.program.pk, user=self.officer, data={'version': self.program.version, 'notes': 'Synthetic proof',
            'label': 'Synthetic question', 'kind': 'text', 'is_required': True, 'is_active': True, 'position': 0})
        self.program.refresh_from_db()
        self.record()
        with self.assertRaises(ValidationError):
            save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(slots=6))
        self.assertFalse(self.program.applications.exists())

    def test_never_published_draft_cannot_record_legacy_attestation(self):
        with self.assertRaises(ValidationError):
            self.record(kind='legacy', approval_date='', signatory='')
        self.assertFalse(PDAOApprovalRecord.objects.exists())

    def test_changed_preliminary_draft_snapshot_requires_fresh_explicit_capture(self):
        first = self.capture()
        self.program = save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(slots=4))
        approval = self.record()
        with self.assertRaises(ValidationError):
            self.bind(first, approval)
        second = self.capture()
        self.assertEqual(second.number, 2)
        self.assertNotEqual(first.digest, second.digest)
        self.bind(second, approval)
        first.refresh_from_db()
        self.assertEqual(first.snapshot['program']['slots'], 1)

    def test_form_validated_before_approval_cannot_save_after_freeze(self):
        form = ProgramForm(self.edit_data(slots=4), instance=self.program)
        self.assertTrue(form.is_valid())
        self.record()
        with self.assertRaises(ValidationError):
            form.save()
        self.program.refresh_from_db()
        self.assertEqual(self.program.slots, 1)


class ApprovedTermsConcurrencyTests(TermsHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_terms(draft=True)

    def race(self, first, second):
        barrier = Barrier(2)
        def worker(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    action()
                    return True
                except ValidationError:
                    return False
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, action) for action in (first, second)]
            return [future.result(timeout=30) for future in futures]

    def test_concurrent_bindings_only_one_stale_counter_wins(self):
        revision, approval = self.capture(), self.record()
        results = self.race(lambda: self.bind(revision, approval, version=1), lambda: self.bind(revision, approval, version=1))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(ProgramApprovalBinding.objects.count(), 1)
        self.assertEqual(ProgramLog.objects.filter(action='approval_bound').count(), 1)

    def test_concurrent_approval_record_and_edit_cannot_approve_silently_changed_terms(self):
        data = self.edit_data(slots=9)
        results = self.race(self.record, lambda: save_program(pk=self.program.pk, user=self.officer, data=data))
        self.assertCountEqual(results, [True, False])
        self.assertFalse(ProgramApprovalBinding.objects.exists())

    def test_concurrent_bind_and_publish_cannot_publish_without_binding(self):
        revision, approval = self.capture(), self.record()
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            results = self.race(lambda: self.bind(revision, approval, version=1),
                lambda: change_publication(self.program.pk, user=self.officer, version=0, action='published', notes='Synthetic publish'))
        self.assertTrue(results[0])
        self.program.refresh_from_db()
        if self.program.status == 'published':
            self.assertTrue(ProgramApprovalControl.objects.get().active_binding_id)

    def test_concurrent_capture_and_edit_never_binds_stale_terms(self):
        digest = terms_digest(snapshot_terms(self.program))
        result = self.race(lambda: self.capture(digest=digest, program_version=0),
                          lambda: save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(slots=7)))
        self.assertTrue(result[1])
        self.program.refresh_from_db()
        self.assertEqual(self.program.slots, 7)
        if result[0]:
            revision = ProgramTermsRevision.objects.get()
            approval = self.record()
            with self.assertRaises(ValidationError):
                self.bind(revision, approval)

    def test_concurrent_submission_and_binding_replacement_preserve_original_history(self):
        private_media(self)
        # Seed a synthetic operating legacy program, then explicitly reconcile it.
        Program.objects.filter(pk=self.program.pk).update(status='published', published_at=timezone.now(), policy_authorized_at=timezone.now())
        self.program.refresh_from_db()
        binding = self.reconcile()
        newer = self.record()
        member = create_member('SYNTHETIC-CONCURRENT-BINDING')
        member.refresh_from_db()
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            verified = verify_member(self.program.pk, **verification(member, self.program))
            results = self.race(lambda: self.bind(binding.revision, newer),
                lambda: submit_application(self.program.pk, grant=verified, data={'version': 0},
                    files=MultiValueDict({'calendar_photo': [image_upload()]})))
            self.assertTrue(results[0])
            if results[1]:
                self.assertEqual(ProgramApplication.objects.get().source_snapshot['approval_binding'], binding.pk)
            else:
                self.assertFalse(ProgramApplication.objects.exists())
            with self.assertRaises(ValidationError):
                submit_application(self.program.pk, grant=verified, data={'version': 0}, files=MultiValueDict())


class ApprovedTermsMigrationTests(TermsHelpers, TransactionTestCase):
    def test_additive_schema_preserves_program_and_approval_without_automatic_binding(self):
        self.setup_terms()
        self.record()
        before = Program.objects.filter(pk=self.program.pk).values().get()
        approvals = list(PDAOApprovalRecord.objects.values())
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('programs', '0004_pdaoapprovalrecord')])
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration('programs', '0005_approved_terms')
            self.assertFalse(any(op.__class__.__name__ in ('RunPython', 'RunSQL', 'RemoveField', 'AlterField', 'DeleteModel') for op in migration.operations))
            executor.migrate(leaves)
            self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)
            self.assertEqual(list(PDAOApprovalRecord.objects.values()), approvals)
            self.assertFalse(ProgramTermsRevision.objects.exists())
            self.assertFalse(ProgramApprovalBinding.objects.exists())
            self.assertFalse(ProgramApprovalControl.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
