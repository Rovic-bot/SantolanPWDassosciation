"""Aggregate accuracy, privacy and program-first selection boundaries."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceCase, EligibilityStatus
from members.tests import create_member
from membership.tests import grant
from .models import Program, ProgramApplication, ProgramLog
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class ApplicationWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('synthetic_review_admin')
        now = timezone.now()
        cls.medical = create_program(name='Medical Access Week', public_code='SP-000001', assistance_type='Healthcare & Medical Aid', slots=2)
        cls.closed = create_program(name='Financial Assistance Q4', public_code='SP-000002', assistance_type='Financial', slots=None,
            registration_opens_at=now-timedelta(days=10),registration_closes_at=now-timedelta(days=1))
        cls.draft = create_program(name='Nutrition Support', public_code='SP-000003', slots=8)
        Program.objects.filter(pk=cls.draft.pk).update(status='draft',published_at=None)
        for code,label in [('eligible','Eligible'),('ineligible','Ineligible')]:
            EligibilityStatus.objects.get_or_create(code=code,defaults={'label':label})
        cls.apps=[]
        for index,status in enumerate(('PENDING_PHOTO_VERIFICATION','ELIGIBLE','NEEDS_INFORMATION','COMPLETED')):
            app=ProgramApplication.objects.create(program=cls.medical,member=create_member(f'SYNTH-REVIEW-{index}'),
                public_reference=f'SYNTH-PRIVATE-REF-{index}',status=status)
            cls.apps.append(app)
            if index:
                code='ineligible' if index==2 else 'eligible'
                AssistanceCase.objects.create(application=app,eligibility_id=code,eligibility_label=code,
                    reviewed_at=now,member_version=0,program_version=0,review_notes='PRIVATE CASE NOTES',
                    decision='approved' if index==1 else 'pending')

    def setUp(self):
        self.client.force_login(self.admin)
        self.url=reverse('application_workspace')

    def test_alias_and_original_route_are_private_read_only_and_program_first(self):
        for url in (self.url,self.url+'/',reverse('core:application_programs')):
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertIn('no-store',response['Cache-Control'])
            self.assertContains(response,'Program review selection')
            self.assertContains(response,'aria-current="page">Program Applications &amp; Eligibility')
            self.assertEqual(self.client.post(url).status_code,405)
            self.assertEqual(self.client.head(url).status_code,200)
            for app in self.apps:
                self.assertNotContains(response,app.public_reference)
                self.assertNotContains(response,app.member.control_number)
            self.assertNotContains(response,'PRIVATE CASE NOTES')
        self.assertEqual(ProgramLog.objects.count(),0)

    def test_live_totals_and_recorded_eligibility_denominator_ignore_filters(self):
        response=self.client.get(self.url,{'q':self.medical.public_code})
        self.assertEqual([x['value'] for x in response.context['review_metrics']],[3,4,1,67])
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertContains(response,'Of recorded eligible / ineligible outcomes')
        Program.objects.filter(pk=self.medical.pk).update(policy_authorized_at=None)
        self.assertEqual(self.client.get(self.url).context['review_metrics'][2]['value'],0)

    def test_demand_is_not_a_beneficiary_allocation_and_statuses_reconcile(self):
        item=self.client.get(self.url,{'q':self.medical.public_code}).context['selected_program']
        self.assertEqual((item['applications'],item['demand'],item['progress'],item['excess']),(4,200,100,2))
        self.assertEqual(item['available'],'1 unallocated')
        self.assertEqual(sum(x['count'] for x in item['statuses']),4)
        self.assertEqual(item['eligibility'],'2 eligible / 1 ineligible recorded')
        self.assertEqual(item['review_url'],reverse('programs:applications',args=[self.medical.pk]))
        self.assertEqual(item['accent'],'blue')

    def test_selection_is_scoped_to_visible_programs_and_zero_counts_disable_review(self):
        response=self.client.get(self.url,{'selected':str(self.draft.pk)})
        self.assertEqual(response.context['selected_program']['id'],str(self.draft.pk))
        self.assertContains(response,'disabled data-preview-disabled>')
        response=self.client.get(self.url,{'q':self.medical.public_code,'selected':str(self.draft.pk)})
        self.assertEqual(response.context['selected_program']['id'],str(self.medical.pk))
        response=self.client.get(self.url,{'q':'Nothing matches'})
        self.assertContains(response,'No programs found')
        self.assertNotContains(response,'id="selected-program-panel"')
        self.assertEqual(response.context['review_programs'],[])

    def test_closed_filter_and_missing_capacity_keep_existing_meanings(self):
        response=self.client.get(self.url,{'status':'closed'})
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        row=response.context['selected_program']
        self.assertEqual(row['status'],'published')
        self.assertEqual(row['registration_state'],'Registration closed')
        self.assertIsNone(row['demand'])
        self.assertEqual(row['schedule'],'Not scheduled')
        self.assertEqual(row['available'],'Capacity not set')

    def test_permissions_do_not_expose_cases_or_allocations_to_application_only_viewer(self):
        user=get_user_model().objects.create_user('synthetic_review_viewer',is_staff=True)
        grant(user,'accounts.access_dashboard','programs.view_program')
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code,403)
        grant(user,'programs.view_programapplication')
        response=self.client.get(self.url,{'q':self.medical.public_code})
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.context['review_metrics'][3]['value'])
        self.assertEqual(response.context['selected_program']['available'],'Usage restricted')
        self.assertEqual(response.context['selected_program']['eligibility'],'Eligibility access restricted')
        self.assertNotContains(response,'1 unallocated')
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)

    def test_pagination_escaping_and_unrelated_assets(self):
        for index in range(21):
            create_program(name=f'Synthetic paged program {index:02d}')
        response=self.client.get(self.url,{'q':'Synthetic paged','sort':'az','page':2})
        self.assertEqual(len(response.context['review_programs']),1)
        self.assertContains(response,'Synthetic paged program 20')
        self.assertContains(response,'data-review-page')
        Program.objects.filter(pk=self.medical.pk).update(name='<script>unsafe title</script>')
        response=self.client.get(self.url,{'q':self.medical.public_code})
        self.assertNotContains(response,'<script>unsafe title</script>')
        for route in ('core:home','core:dashboard','program_portfolio','event_workspace','member_directory','program_builder','admin:index'):
            response=self.client.get(reverse(route))
            self.assertEqual(response.status_code,200)
            self.assertNotContains(response,'css/application-workspace.css')
            self.assertNotContains(response,'js/application-workspace.js')
