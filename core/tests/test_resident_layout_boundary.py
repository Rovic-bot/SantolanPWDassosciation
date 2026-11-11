"""Shared print and failure templates must not restyle staff screens."""
from uuid import UUID

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse


class ResidentLayoutBoundaryTests(SimpleTestCase):
    key = UUID('00000000-0000-4000-8000-000000000001')

    def render_for(self, route, template, *, args=None, **context):
        request = RequestFactory().get(reverse(route, args=args))
        request.resolver_match = resolve(request.path)
        request.user = AnonymousUser()
        return render_to_string(template, context, request=request)

    def test_source_print_layout_is_isolated_from_both_portal_themes(self):
        resident = self.render_for('membership:pdao_prepare', 'membership/registration/pdao_print.html')
        staff = self.render_for('membership:pdao_print', 'membership/pdao/print.html',
                               args=[self.key], registration={'pk': self.key})
        self.assertNotIn('css/public-resident.css', resident)
        self.assertNotIn('css/public-resident.css', staff)
        self.assertNotIn('css/public-make.css', resident)
        self.assertNotIn('css/public-make.css', staff)
        self.assertIn('css/pdao-print.css', resident)
        self.assertIn('css/pdao-print.css', staff)
        self.assertIn('PDAO consent statement', resident)
        self.assertIn('PDAO consent statement', staff)

    def test_shared_error_and_unavailable_screens_respect_route_boundary(self):
        for template in ('403.html', '404.html', 'membership/registration/unavailable.html'):
            with self.subTest(template=template):
                self.assertIn('css/public-resident.css', self.render_for('membership:registration_apply', template))
                self.assertNotIn('css/public-resident.css', self.render_for('membership:registration_inbox', template))
                self.assertIn('css/public-make.css', self.render_for('membership:registration_apply', template))
                self.assertNotIn('css/public-make.css', self.render_for('membership:registration_inbox', template))

    def test_staff_sign_in_stays_separate_from_resident_layout(self):
        html = self.render_for('accounts:login', 'accounts/login.html')
        self.assertNotIn('css/public-make.css', html)
        self.assertNotIn('portal-redesign', html)
