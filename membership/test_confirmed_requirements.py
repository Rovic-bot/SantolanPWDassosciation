"""Owner-updated PDF checklist and retained privacy/CMS behavior; synthetic data."""
from html.parser import HTMLParser
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.content import save_content
from core.models import ContentRevision, PublicContent
from documents.models import DocumentType, DocumentVerification, MembershipDocumentRequirement
from members.models import DisabilityType, Member
from members.tests import create_member
from membership.forms import ApplicationForm
from membership.models import MembershipApplication, MembershipEvent, MembershipSettings
from membership.services import submit_application
from membership.tests import onsite_profile, grant, profile


ASSOCIATION_LABELS = [
    'One (1) long brown envelope', 'Four (4) photocopies of PWD ID',
    "Two (2) photocopies of Voter's Certificate",
    'Two (2) photocopies of Birth Certificate OR Marriage Certificate',
    'Four (4) 2×2 pictures with white background',
]
PDAO_LABELS = [
    'PDAO PWD ID Application Form', 'One (1) 1×1 ID Picture', 'Proof of Life',
    'Medical Certificate stating:', 'Birth Certificate OR Marriage Certificate',
    "Voter's ID OR Voter's Certificate OR National ID",
]


class RequirementLists(HTMLParser):
    """Read numbered requirements, preserving nested medical-detail text."""
    def __init__(self, html):
        super().__init__()
        self.items = {}
        self.current = None
        self.depth = 0
        self.in_label = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'ol' and dict(attrs).get('id') in ('association-requirements', 'pdao-requirements'):
            self.current = dict(attrs)['id']
            self.items[self.current] = []
        elif self.current and tag == 'li':
            if self.depth == 0:
                self.parts, self.label = [], []
            self.depth += 1
        elif self.current and tag == 'strong' and self.depth == 1:
            self.in_label = True

    def handle_endtag(self, tag):
        if self.current and tag == 'li':
            self.depth -= 1
            if self.depth == 0:
                self.items[self.current].append({
                    'label': ' '.join(''.join(self.label).split()),
                    'text': ' '.join(' '.join(self.parts).split()),
                })
        elif tag == 'strong':
            self.in_label = False
        elif tag == 'ol':
            self.current = None

    def handle_data(self, data):
        if self.current and self.depth:
            self.parts.append(data)
            if self.in_label:
                self.label.append(data)


class ConfirmedMembershipGuidanceTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        setting = override_settings(MEDIA_ROOT=media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.admin = get_user_model().objects.create_superuser('confirmed_guidance_admin')
        self.route = reverse('core:membership')

    def lists(self, response):
        self.assertEqual(response.status_code, 200)
        return RequirementLists(response.content.decode()).items

    def assert_association(self, response):
        items = self.lists(response)['association-requirements']
        self.assertEqual([item['label'] for item in items], ASSOCIATION_LABELS)
        self.assertIn('either civil document; both are not required', items[3]['text'])
        self.assertIn('physical item', items[0]['text'])
        self.assertIn('not a required digital upload', items[0]['text'])
        self.assertContains(response, 'Membership Application Form')
        return items

    def test_public_exact_five_items_and_onsite_procedure_without_accounts_or_uploads(self):
        response = self.client.get(self.route)
        self.assert_association(response)
        self.assertContains(response, 'In-person requirements review and verification remain required')
        self.assertContains(response, 'Three application channels')
        self.assertContains(response, 'Online submission is not membership approval')
        self.assertContains(response, 'No member login account is needed')
        self.assertNotContains(response, '<form')
        self.assertNotContains(response, 'type="file"')
        self.assertNotContains(response, 'type="password"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.head(self.route).status_code, 200)
        self.assertEqual(self.client.post(self.route, profile()).status_code, 405)
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_pdao_six_items_medical_details_and_renewal_stay_outside_association_list(self):
        response = self.client.get(self.route)
        items = self.lists(response)['pdao-requirements']
        self.assertEqual([item['label'] for item in items], PDAO_LABELS)
        self.assertIn('Whole-body photograph holding an updated calendar', items[2]['text'])
        for detail in ('Final diagnosis', 'Functional limitation', "Doctor's name", "Doctor's license number"):
            self.assertIn(detail, items[3]['text'])
        self.assertContains(response, 'PDAO Renewal Only')
        self.assertContains(response, 'Surrender of the original old or expired PWD ID')
        self.assertContains(response, 'Confirm the latest requirements directly with PDAO')
        self.assertContains(response, 'PDAO proof of life and assistance-program identity evidence are separate')
        self.assertNotIn('surrender', ' '.join(item['text'] for item in items))
        self.assert_association(response)
        self.assertFalse(MembershipDocumentRequirement.objects.filter(capture_key__isnull=True).exists())

    def test_upload_configuration_is_retained_privately_and_does_not_override_confirmed_list(self):
        requirement = MembershipDocumentRequirement.objects.create(
            document_type=DocumentType.objects.create(name='Synthetic legacy upload', description='Not public personal evidence.'),
            instructions='Legacy digital instructions.', is_required=True)
        before = list(MembershipDocumentRequirement.objects.values())
        public = self.client.get(self.route)
        self.assert_association(public)
        self.assertNotContains(public, 'Synthetic legacy upload')
        self.assertNotContains(public, 'Not public personal evidence')
        self.client.force_login(self.admin)
        intake = self.client.get(reverse('membership:encode'))
        self.assert_association(intake)
        self.assertContains(intake, 'Synthetic legacy upload')
        self.assertContains(intake, 'does not mark an item received or verified')
        form = intake.context['form']
        self.assertIn(f'document_{requirement.pk}', [field.name for field in form.document_fields])
        self.assertEqual(sum(field.field.required for field in form.document_fields), 1)
        self.assertTrue(form.fields[f'document_{requirement.pk}'].required)
        self.assertEqual(list(MembershipDocumentRequirement.objects.values()), before)
        self.assertFalse(DocumentVerification.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())

    def test_pdao_information_and_physical_envelope_add_no_upload_rules_or_approval(self):
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://registry.example.test/'})
        self.client.get(self.route)
        classification = DisabilityType.objects.create(name='Synthetic classification')
        form = ApplicationForm({**onsite_profile(), 'disability_type': classification.pk,
                                'submission_token': ApplicationForm().initial['submission_token']})
        self.assertTrue(all(not field.field.required for field in form.document_fields))
        self.assertTrue(form.is_valid(), form.errors)
        application = submit_application(form, user=self.admin)
        self.assertTrue(all(item.get('capture_key') and not item['required'] for item in application.requirements_snapshot))
        self.assertEqual(application.documents.count(), 0)
        self.assertEqual(application.status, 'pending')
        self.assertIsNone(application.prpwd_verified)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(DocumentVerification.objects.exists())

    def test_approved_members_and_historical_evidence_are_unchanged_by_guidance_views(self):
        member = create_member('CONFIRMED-HISTORY')
        member.application.requirements_snapshot = [{'id': 9999, 'label': 'Historical evidence', 'required': True}]
        member.application.save(update_fields=['requirements_snapshot'])
        before_member = Member.objects.values().get(pk=member.pk)
        before_application = MembershipApplication.objects.values().get(pk=member.application_id)
        self.client.get(self.route)
        self.client.force_login(self.admin)
        self.assert_association(self.client.get(reverse('membership:encode')))
        review = self.client.get(reverse('membership:detail', args=[member.application.reference]))
        self.assert_association(review)
        self.assertContains(review, 'Historical evidence')
        self.assertContains(review, 'An official member record has been created')
        self.assertEqual(Member.objects.values().get(pk=member.pk), before_member)
        self.assertEqual(MembershipApplication.objects.values().get(pk=member.application_id), before_application)
        self.assertFalse(MembershipEvent.objects.exists())
        self.assertFalse(DocumentVerification.objects.exists())

    def test_intake_and_review_remain_private_for_anonymous_nonstaff_and_unprivileged_staff(self):
        member = create_member('PRIVATE-REVIEW')
        routes = (reverse('membership:encode'), reverse('membership:detail', args=[member.application.reference]))
        for route in routes:
            self.assertEqual(self.client.get(route).status_code, 302)
        for staff in (False, True):
            user = get_user_model().objects.create_user(f'restricted_{staff}', is_staff=staff)
            self.client.force_login(user)
            for route in routes:
                self.assertEqual(self.client.get(route).status_code, 403 if staff else 302)
                self.assertEqual(self.client.post(route, {}).status_code, 403 if staff else 302)

    def test_membership_cms_published_snapshot_and_contact_are_preserved_while_drafts_stay_private(self):
        for key in ('membership', 'contact'):
            save_content(key, user=self.admin, data={'title': f'Approved {key}',
                'body': f'Published {key} instructions. <script>example()</script>', 'version': 0,
                'action': 'publish', 'reason': 'Approved synthetic guidance.'})
            save_content(key, user=self.admin, data={'title': f'Draft {key}',
                'body': f'Unpublished {key} instructions.', 'version': 1,
                'action': 'draft', 'reason': 'Pending institutional review.'})
        before = list(PublicContent.objects.order_by('key').values())
        response = self.client.get(self.route)
        self.assert_association(response)
        for key in ('membership', 'contact'):
            self.assertContains(response, f'Published {key} instructions.')
            self.assertNotContains(response, f'Unpublished {key} instructions.')
        self.assertContains(response, '&lt;script&gt;example()&lt;/script&gt;')
        self.assertNotContains(response, '<script>example()</script>')
        self.client.force_login(self.admin)
        self.assert_association(self.client.get(reverse('core:content_edit', args=['membership'])))
        self.assertEqual(list(PublicContent.objects.order_by('key').values()), before)
        self.assertEqual(ContentRevision.objects.count(), 4)
        response = self.client.post(reverse('core:content_edit', args=['membership']), {
            'title': 'Approved additional instructions', 'body': 'New explicitly published instructions.',
            'version': 2, 'action': 'publish', 'reason': 'Explicitly approved synthetic update.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(self.route), 'New explicitly published instructions.')
        self.assertEqual(ContentRevision.objects.count(), 5)

    def test_cms_guidance_does_not_grant_publication_permissions_to_editors(self):
        editor = get_user_model().objects.create_user('membership_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'core.view_publiccontent', 'core.change_publiccontent')
        self.client.force_login(editor)
        route = reverse('core:content_edit', args=['membership'])
        self.assert_association(self.client.get(route))
        response = self.client.post(route, {'title': 'Unapproved', 'body': 'Unapproved instructions.',
            'version': 0, 'action': 'publish', 'reason': 'Attempt without permission.'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(PublicContent.objects.exists())
        self.assertFalse(ContentRevision.objects.exists())
