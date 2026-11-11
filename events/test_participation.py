"""Event focus, organizer participation rules, and private application gates remain distinct."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from programs.tests import create_program
from programs.terms import snapshot_terms
from .models import Event, EventRegistration, AnnualObservance
from .services import save_event, change_publication, save_observance, change_observance_publication
from .tests import event_data, create_event
from .test_observance_workflow import draft_data


class EventParticipationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('participation_editor')
        self.viewer = get_user_model().objects.create_user('participation_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'events.view_event')

    def event(self, **changes):
        item = save_event(user=self.admin, data=event_data(**changes))
        # Seed preserved historical configuration for publication/privacy checks.
        # New event creation intentionally ignores these removed controls.
        historical = {key: value for key, value in changes.items()
                      if key in ('event_category', 'target_audience', 'who_may_participate')}
        if historical:
            Event.objects.filter(pk=item.pk).update(**historical)
            item.refresh_from_db()
        return item

    def publish(self, item):
        return change_publication(item.pk, user=self.admin, version=item.version,
                                  action='published', notes='Reviewed organizer participation rules.')

    def test_one_event_list_includes_historical_categories_and_separate_observances(self):
        general = self.publish(self.event(title='General community gathering'))
        specific = self.publish(self.event(title='Specific disability awareness activity', event_category='specific',
            target_audience='Deaf people and their families', who_may_participate='Everyone, including neighbors and supporters.'))
        observance = save_observance(user=self.admin, data=draft_data(title='Specific annual observance'))
        change_observance_publication(observance.pk, user=self.admin, version=observance.version,
                                     action='published', notes='Reviewed observance information.')
        general_page = self.client.get(reverse('core:events'), {'category': 'general'})
        self.assertContains(general_page, general.title)
        self.assertContains(general_page, specific.title)
        self.assertNotContains(general_page, 'name="category"')
        self.assertContains(general_page, observance.title)
        specific_page = self.client.get(reverse('core:events'), {'category': 'specific'})
        self.assertContains(specific_page, specific.title)
        self.assertContains(specific_page, observance.title)
        self.assertContains(specific_page, general.title)
        detail = self.client.get(reverse('events:detail', args=[specific.pk]), {'popup': '1'})
        self.assertContains(detail, specific.target_audience)
        self.assertContains(detail, specific.who_may_participate)
        self.assertNotContains(detail, 'Online applications for the linked program')
        self.assertEqual(self.client.post(reverse('events:register', args=[general.pk]), {}).status_code, 410)
        self.assertFalse(EventRegistration.objects.exists())

    def test_uncategorized_event_can_publish_but_observance_rules_still_apply(self):
        item = self.publish(self.event(event_category=''))
        self.assertEqual(item.status, 'published')
        self.assertEqual(item.history.count(), 2)
        observance = save_observance(user=self.admin, data=draft_data(who_may_participate=''))
        with self.assertRaises(ValidationError):
            change_observance_publication(observance.pk, user=self.admin, version=observance.version,
                                         action='published', notes='Incomplete rules.')
        self.assertEqual(observance.revisions.count(), 1)

    def test_public_legacy_events_are_listed_but_drafts_archives_and_future_publications_are_not(self):
        draft = self.event(title='Private activity')
        legacy = create_event(title='Unclassified historical activity')
        future = self.publish(self.event(title='Future publication'))
        Event.objects.filter(pk=future.pk).update(published_at=timezone.now()+timezone.timedelta(days=1))
        archived = self.publish(self.event(title='Archived activity'))
        change_publication(archived.pk, user=self.admin, version=archived.version, action='archived', notes='Archive.')
        response = self.client.get(reverse('core:events'))
        for item in (draft, future, archived):
            self.assertNotContains(response, item.title)
        self.assertContains(response, legacy.title)
        self.assertEqual(self.client.get(reverse('events:detail', args=[legacy.pk]), {'popup': '1'}).status_code, 200)

    def test_past_filter_and_cancellation_are_explicit(self):
        past = self.publish(self.event(title='Past general activity', starts_at=timezone.now()-timezone.timedelta(days=2),
                                      ends_at=timezone.now()-timezone.timedelta(days=1)))
        cancelled = self.publish(self.event(title='Cancelled general activity'))
        change_publication(cancelled.pk, user=self.admin, version=cancelled.version, action='cancelled', notes='Cancelled.')
        self.assertNotContains(self.client.get(reverse('core:events')), past.title)
        self.assertContains(self.client.get(reverse('core:events'), {'period': 'past', 'category': 'general'}), past.title)
        self.assertContains(self.client.get(reverse('events:detail', args=[cancelled.pk]), {'popup': '1'}), 'This event has been cancelled.')

    def test_observance_rules_are_in_immutable_history_and_public_details_use_an_allowlist(self):
        item = save_observance(user=self.admin, data=draft_data(target_audience='Focused community',
            who_may_participate='Anyone may join organizer-approved activities.'))
        original = item.revisions.get()
        item = change_observance_publication(item.pk, user=self.admin, version=item.version,
                                             action='published', notes='Review complete.')
        detail = self.client.get(reverse('events:observance_public_detail', args=[item.pk]))
        self.assertContains(detail, 'Focused community')
        self.assertContains(detail, 'Anyone may join organizer-approved activities.')
        self.assertNotIn('published_by_label', detail.context['observance'])
        self.assertNotIn('revisions', detail.context['observance'])
        change_observance_publication(item.pk, user=self.admin, version=item.version,
                                      action='draft', notes='Prepare revised instructions.')
        self.assertEqual(self.client.get(reverse('events:observance_public_detail', args=[item.pk])).status_code, 404)
        original.refresh_from_db()
        self.assertEqual(original.who_may_participate, 'Anyone may join organizer-approved activities.')
        with self.assertRaises(ValidationError):
            original.save()

    def test_public_audience_text_is_escaped_and_mutations_require_permissions(self):
        item = self.publish(self.event(target_audience='<script>target()</script>',
            who_may_participate='<img src=x onerror=rules()>'))
        for url in (reverse('core:events'), reverse('events:detail', args=[item.pk])):
            response = self.client.get(url, {'popup': '1'})
            self.assertNotContains(response, '<script>target()</script>')
            self.assertNotContains(response, '<img src=x onerror=rules()>')
        detail = self.client.get(reverse('events:detail', args=[item.pk]), {'popup': '1'})
        self.assertContains(detail, '&lt;script&gt;target()&lt;/script&gt;')
        self.assertContains(detail, '&lt;img src=x onerror=rules()&gt;')
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('events:create')).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_event(user=self.viewer, data=event_data())
        self.client.force_login(self.admin)
        page = self.client.get(reverse('events:create'))
        for field in ('event_category', 'target_audience', 'who_may_participate'):
            self.assertNotContains(page, f'name="{field}"')
        existing = self.client.get(reverse('events:edit', args=[item.pk]))
        for field in ('event_category', 'target_audience', 'who_may_participate'):
            self.assertNotContains(existing, f'name="{field}"')

    def test_stale_edits_and_audit_failure_preserve_historical_fields(self):
        item = self.event(target_audience='Historical focus')
        updated = save_event(user=self.admin, pk=item.pk,
            data=event_data(version=item.version, title='Updated title', target_audience='Ignored focus'))
        with self.assertRaises(ValidationError):
            save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version))
        with patch('events.services.record_log', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                save_event(user=self.admin, pk=item.pk,
                    data=event_data(version=updated.version, title='Uncommitted title', who_may_participate='Uncommitted rules'))
        updated.refresh_from_db()
        self.assertEqual(updated.title, 'Updated title')
        self.assertEqual(updated.target_audience, 'Historical focus')
        self.assertNotEqual(updated.who_may_participate, 'Uncommitted rules')
        self.assertIn('title', updated.history.first().changes)
        self.assertNotIn('target_audience', updated.history.first().changes)

    def test_protected_program_link_keeps_existing_terms_and_audience_rules(self):
        program = create_program()
        item = create_event(application_program=program, event_category='specific')
        before = snapshot_terms(program)
        with self.assertRaises(ValidationError):
            save_event(user=self.admin, pk=item.pk, data=event_data(title='Changed protected title', event_category='specific',
                application_program=program.pk, target_audience='Changed focus'))
        self.assertEqual(snapshot_terms(program), before)
        self.assertNotIn('target_audience', before['event'])
        self.assertNotIn('who_may_participate', before['event'])
