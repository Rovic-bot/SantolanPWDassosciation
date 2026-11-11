"""Persistent synthetic preparation using the already-validated service fixture.

The disposable runner's capability is neither reused nor patched. A separate
strict manifest/server-identity check authorizes only this dedicated demo DB.
"""
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from datetime import timedelta
from fractions import Fraction

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import override_settings

from assistance.tests import seed_statuses
from assistance.models import AssistanceRelease
from documents.models import DocumentType, MembershipDocumentRequirement
from members.models import Member, DisabilityType
from membership.models import MembershipSettings
from membership.test_registration_handoff import acceptance_policy
from membership.test_pdf_registration import pdf_policy
from ewaf.test_synthetic_twelve import SyntheticTwelveIntegrationTests as Tested, BASE, NOW, oracle, proposal
from ewaf import dataset_methods as methods, vault_services as vault
from ewaf.operational_models import OperationalRun
from scripts.ewaf_twelve_demo_web import verify_connection


class Fixture(TestCase):
    # These helpers call the real registration, approval, verification, eligibility,
    # release, evidence and ranking services. No test lifecycle or guard is invoked.
    observe = Tested.observe
    handoff_form = Tested.handoff_form
    register_members = Tested.register_members
    program = Tested.program
    publish = Tested.publish
    apply = Tested.apply
    history = Tested.history
    bind = Tested.bind
    findings = Tested.findings
    accept = Tested.accept
    generate = Tested.generate


def seed():
    verify_connection(connection=connection)
    manifest = settings.EWAF_TWELVE_DEMO
    if Member.objects.exists() or get_user_model().objects.exists():
        raise RuntimeError('Refusing to seed over existing users or member data.')
    fixture = Fixture()
    summary = {'purpose': manifest['purpose'], 'members': [], 'scenarios': [], 'qualifying_releases': 27}
    with transaction.atomic(), patch('django.utils.timezone.now', return_value=NOW):
        seed_statuses()
        fixture.actor = fixture.user = get_user_model().objects.create_superuser(
            manifest['admin_username'], email='ewaf-demo@example.test', password=manifest['admin_password'])
        fixture.doc_type = DocumentType.objects.create(name='SYNTHETIC reviewed income, household, employment and ledger coverage')
        fixture.requirement = MembershipDocumentRequirement.objects.create(document_type=fixture.doc_type)
        DisabilityType.objects.get_or_create(name='Visual Disability')
        MembershipSettings.objects.create(pk=1, prpwd_url='https://registry.example.test/manual')
        fixture.policy = acceptance_policy() | pdf_policy() | {'onsite_enabled': True, 'handoff_enabled': True}
        fixture.members, fixture.apps, fixture.proofs, fixture.releases = {}, {}, {}, []
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=fixture.policy):
            with patch('django.utils.timezone.now', return_value=BASE - timedelta(days=20)):
                fixture.register_members()
            fixture.history()
            # Balanced is last, so the Vault initially opens on the primary vector.
            for scenario in ('ses', 'es', 'pa', 'hm', 'balanced'):
                with patch('django.utils.timezone.now', return_value=BASE):
                    for status in ('DRAFT', 'LOCKED'):
                        fixture.weights = vault.record_ses_weights(user=fixture.user, expected=vault.token(),
                            proposal=proposal(scenario), reason='SYNTHETIC persistent demo ' + scenario,
                            status=status, method=methods.COMPOSITE)
                    title = 'Balanced' if scenario == 'balanced' else scenario.upper() + ' Focus'
                    fixture.target = fixture.program('EWAF DEMO - ' + title + ' - 12 fictional members', ewaf=True,
                        opens=BASE + timedelta(hours=1), closes=BASE + timedelta(days=1))
                    fixture.bind()
                    fixture.publish(fixture.target)
                fixture.apps = {}
                with patch('django.utils.timezone.now', return_value=BASE + timedelta(hours=2)):
                    for label, member in fixture.members.items():
                        fixture.apps[label] = fixture.apply(fixture.target, member)
                for label in fixture.members:
                    fixture.accept(label)
                run = fixture.generate()
                run.clean()
                expected = oracle(fixture.weights.validation['weights'])
                for label, app in fixture.apps.items():
                    result = run.calculations[str(app.pk)]
                    fixture.assertEqual(Fraction(result['score_exact']) * 100, expected[label]['score'])
                    fixture.assertEqual(result['comparison']['business_rank'], expected[label]['rank'])
                top = next(label for label, result in expected.items() if result['rank'] == 1)
                summary['scenarios'].append({'name': title, 'scenario': scenario, 'program_id': str(fixture.target.pk),
                    'run_id': run.pk, 'expected_top': fixture.members[top].full_name,
                    'weights': fixture.weights.validation['weights'], 'primary': scenario == 'balanced'})
                print('Prepared', title, '- 12 accepted applications; exact rankings verified.', flush=True)
        fixture.assertEqual(Member.objects.count(), 12)
        fixture.assertEqual(AssistanceRelease.objects.filter(voided_at__isnull=True).count(), 27)
        fixture.assertEqual(OperationalRun.objects.count(), 5)
        summary['members'] = [{'label': label, 'name': member.full_name, 'member_id': member.pk,
            'control_number': member.control_number} for label, member in fixture.members.items()]
        summary['scenarios'].sort(key=lambda item: not item['primary'])
    directory = Path(settings.BASE_DIR) / '.local/ewaf-twelve-demo'
    (directory / 'seed-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    # Preserve the exact synthetic intake procedure for subsequent manual testing.
    (directory / 'registration-policy.json').write_text(json.dumps(fixture.policy, indent=2), encoding='utf-8')
    return summary
