from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from announcements.tests import image_upload
from .forms import EventForm
from .models import Event
from .services import publish_event, save_event
from .tests import event_data


class OptionalEventDetailsTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.admin = get_user_model().objects.create_superuser('optional_event_admin')
        self.client.force_login(self.admin)

    def test_blank_optional_fields_publish_from_row_and_remain_publicly_listed(self):
        for category in ('general', 'specific'):
            item = save_event(user=self.admin, data=event_data(title=f'Optional {category} event',
                event_category=category, target_audience='', who_may_participate=''))
            response = self.client.post(reverse('events:manage_detail', args=[item.pk]),
                {'action': 'published', 'version': item.version, 'return_to': 'list'}, follow=True)
            self.assertRedirects(response, reverse('events:manage_list'))
            self.assertNotContains(response, 'before publishing')
            item.refresh_from_db()
            self.assertEqual(item.status, 'published')
            self.assertEqual(item.history.filter(action='published').count(), 1)
            self.assertContains(self.client.get(reverse('core:events'), {'category': 'general'}), item.title)
            detail = self.client.get(reverse('events:detail', args=[item.pk]), {'popup': '1'})
            self.assertContains(detail, item.title)
            self.assertNotContains(detail, 'has not yet published the target audience')
            self.assertNotContains(detail, 'Participation rules have not yet been published')
            item = save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version,
                event_category=category, target_audience='', who_may_participate=''))
            self.assertEqual(item.status, 'published')

    def test_event_form_omits_image_description_and_upload_generates_accessible_text(self):
        form = EventForm(user=self.admin)
        self.assertNotIn('image_alt', form.fields)
        for field in ('event_category', 'target_audience', 'who_may_participate', 'capacity', 'application_program'):
            self.assertNotIn(field, form.fields)
        page = self.client.get(reverse('events:create'))
        self.assertNotContains(page, 'name="image_alt"')
        item = save_event(user=self.admin, data=event_data(title='Community gathering',
            target_audience='', who_may_participate='', image_alt='Untrusted hidden value'),
            files=MultiValueDict({'image': [image_upload()]}))
        self.assertEqual(item.image_alt, 'Event image for Community gathering')
        self.assertEqual(item.history.get().changes['image_alt']['after'], item.image_alt)
        item = publish_event(item.pk, user=self.admin, version=item.version)
        self.assertContains(self.client.get(reverse('events:detail', args=[item.pk]), {'popup': '1'}),
            'alt="Event image for Community gathering"')

    def test_new_events_default_to_general_without_intake_configuration(self):
        from programs.tests import create_program
        program = create_program()
        page = self.client.get(reverse('events:create'))
        for field in ('event_category', 'target_audience', 'who_may_participate', 'capacity', 'application_program'):
            self.assertNotContains(page, f'name="{field}"')
        item = save_event(user=self.admin, data=event_data(
            event_category='specific', target_audience='Hidden submitted audience',
            who_may_participate='Hidden submitted instructions', capacity='10',
            application_program=str(program.pk)))
        item.refresh_from_db()
        self.assertEqual(item.event_category, 'general')
        self.assertEqual(item.target_audience, '')
        self.assertEqual(item.who_may_participate, '')
        self.assertIsNone(item.capacity)
        self.assertIsNone(item.application_program_id)
        self.assertEqual(item.history.get().changes['event_category']['after'], 'general')

    def test_existing_event_settings_are_preserved_and_detail_actions_are_simplified(self):
        from .tests import create_event
        item = create_event(capacity=50, event_category='specific',
            target_audience='Saved audience', who_may_participate='Saved participation guidance')
        form = EventForm(instance=item, user=self.admin)
        self.assertEqual(form.initial['capacity'], 50)
        self.assertEqual([field.name for field in form.visible_fields()],
                         [field.name for field in EventForm(user=self.admin).visible_fields()])
        editor = self.client.get(reverse('events:edit', args=[item.pk]))
        self.assertTemplateUsed(editor, 'events/builder/page.html')
        for field in ('event_category', 'application_program', 'capacity', 'target_audience', 'who_may_participate'):
            self.assertNotContains(editor, f'name="{field}"')
        item = save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version,
            title='Edited title', notes='', capacity='1', event_category='general', target_audience='Ignored'))
        self.assertEqual(item.history.first().notes, 'Event updated from the event editor.')
        detail = self.client.get(reverse('events:manage_detail', args=[item.pk]))
        for text in ('Event attendance', 'Legacy registrations', 'View public event', 'Venue planning capacity'):
            self.assertNotContains(detail, text)
        self.assertContains(detail, 'Edit event')
        item.refresh_from_db()
        self.assertEqual(item.capacity, 50)
        self.assertEqual(item.event_category, 'specific')
        self.assertEqual(item.target_audience, 'Saved audience')

    def test_existing_image_description_is_preserved_until_image_replacement_or_removal(self):
        item = save_event(user=self.admin, data=event_data(), files=MultiValueDict({'image': [image_upload()]}))
        Event.objects.filter(pk=item.pk).update(image_alt='Existing descriptive image text')
        item = save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version))
        self.assertEqual(item.image_alt, 'Existing descriptive image text')
        item = save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version, title='New poster'),
            files=MultiValueDict({'image': [image_upload()]}))
        self.assertEqual(item.image_alt, 'Event image for New poster')
        item = save_event(user=self.admin, pk=item.pk,
            data=event_data(version=item.version, remove_image=True))
        self.assertEqual(item.image_alt, '')
        self.assertFalse(item.image)

    def test_legacy_image_without_description_can_publish_with_template_fallback(self):
        item = save_event(user=self.admin, data=event_data(), files=MultiValueDict({'image': [image_upload()]}))
        Event.objects.filter(pk=item.pk).update(image_alt='')
        item = publish_event(item.pk, user=self.admin, version=item.version)
        self.assertEqual(item.image_alt, '')
        self.assertContains(self.client.get(reverse('events:detail', args=[item.pk]), {'popup': '1'}),
            'alt="Event image for Community gathering"')

    def test_agenda_opens_the_existing_full_record_and_editor(self):
        item = save_event(user=self.admin, data=event_data())
        response = self.client.get(reverse('events:manage_list'))
        self.assertContains(response, reverse('events:manage_detail', args=[item.pk]))
        self.assertNotContains(response, 'class="modal fade"')
        self.assertContains(self.client.get(reverse('events:manage_detail', args=[item.pk])), 'Edit event')
