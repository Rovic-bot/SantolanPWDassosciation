"""Install explicit source-integration hooks into the isolated port-8000 checkout."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / '.local/main-testing/runtime'
BACKUP = ROOT / '.local/main-testing/intake-base'


def replace(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Runtime hook requires review; expected exactly one anchor: ' + old[:100])
    return text.replace(old, new, 1)


def install():
    for folder in ('program_intake', 'main_testing'):
        shutil.copytree(ROOT / folder, RUNTIME / folder, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('main_testing_settings.py', 'intake_test_settings.py'):
        shutil.copy2(ROOT / 'config' / name, RUNTIME / 'config' / name)
    shutil.copy2(ROOT / 'scripts/intake_browser.cjs', RUNTIME / 'scripts/intake_browser.cjs')
    patches = {}
    patches['ewaf/evidence.py'] = [(
        "    return canonical({'application': str(application.pk), 'application_version': application.version,",
        "    from program_intake.sources import source_extension\n    return canonical({**source_extension(application), 'application': str(application.pk), 'application_version': application.version,")]
    patches['ewaf/readiness.py'] = [(
        '    for criterion in CRITERIA:',
        '    from program_intake.sources import required_criteria, validate_assessment\n    for criterion in required_criteria(application):'), (
        "                if row.source_manifest.get('evidence_contract_version') != 2:",
        "                if row.source_manifest.get('evidence_contract_version') == 3:\n                    try:\n                        validate_assessment(row, application, context)\n                    except ValidationError as error:\n                        add('criteria', 'SOURCE_REVIEW_REQUIRED: ' + '; '.join(error.messages), row.pk)\n                elif row.source_manifest.get('evidence_contract_version') != 2:")]
    patches['ewaf/operational_policy.py'] = [(
        "    for role in ('functional_need', 'consent', 'accessible_alternative'):",
        "    from program_intake.sources import CONTRACT, policy_findings\n    errors.extend(policy_findings(policy))\n    roles = policy.get('eligibility', {}) if policy.get('source_contract') == CONTRACT else ('functional_need', 'consent', 'accessible_alternative')\n    for role in roles:")]
    patches['ewaf/operational_services.py'] = [(
        "            if len(set(used)) != 3:",
        "            from program_intake.sources import CONTRACT, validate_configuration\n            validate_configuration(program, proposed, evidence)\n            if len(set(used)) != (len(proposed['eligibility']) if proposed.get('source_contract') == CONTRACT else 3):"), (
        "                pr = CriterionAssessment.objects.filter(application=application, criterion='PR').first()\n                if not pr or pr.policy_id != configuration.evidence_policy_id:\n                    raise ValidationError('PR: current verified functional-need assessment required')\n                pr.clean()\n                gate = eligibility(pr, configuration.policy['eligibility'])",
        "                from program_intake.sources import program_gate\n                gate = program_gate(application, configuration)")]
    patches['ewaf/operational_forms.py'] = [(
        "                                 for role in ('functional_need', 'consent', 'accessible_alternative')}\n        return result",
        "                                 for role in ('functional_need', 'consent', 'accessible_alternative')}\n        from program_intake.sources import uses_sources\n        if uses_sources(self.configuration):\n            result.update(source_contract=self.configuration.policy['source_contract'], si_requirement=self.configuration.policy['si_requirement'])\n            result['eligibility'] = {role: rule for role, rule in result['eligibility'].items() if any(rule.values())}\n        return result")]
    patches['ewaf/evidence_views.py'] = [(
        "    if criterion == 'PR' and request.method == 'GET':",
        "    from program_intake.sources import configured, uses_sources\n    if criterion in ('SI', 'ES', 'PA', 'ND') and uses_sources(configured(application.program)):\n        return redirect('intake:sources', reference=reference)\n    if criterion == 'PR' and request.method == 'GET':")]
    patches['ewaf/operational_views.py'] = [(
        "    return {'configuration': latest,",
        "    from django.conf import settings\n    return {'auto_source_controls': getattr(settings, 'PROGRAM_INTAKE_ENABLED', False), 'configuration': latest,")]
    patches['templates/ewaf/workspace_configuration.html'] = [(
        '<h2 class="h4">EWAF configuration</h2>',
        '<h2 class="h4">EWAF configuration</h2>\n{% if auto_source_controls and can_authorize %}<p><a href="{% url \'intake:policy\' program.pk %}">Review program data source policy</a></p>{% endif %}')]
    patches['programs/review_services.py'] = [(
        "    if data.get('eligibility') == 'eligible' and application.program.ewaf_applicable:",
        "    from program_intake.sources import has_additional_eligibility\n    if data.get('eligibility') == 'eligible' and application.program.ewaf_applicable and has_additional_eligibility(application):")]
    patches['programs/services.py'] = [(
        "            if not grant_valid(grant, program):",
        "            from program_intake.access import secure_grant\n            if not grant_valid(grant, program) or (getattr(settings, 'PROGRAM_INTAKE_ENABLED', False) and not secure_grant(grant, program)):"), (
        "                source_snapshot={**grant_authorization(program), 'member_id': member.pk,",
        "                source_snapshot={**grant_authorization(program), **({'verification_method': grant['verification_method']} if grant.get('verification_method') else {}), 'member_id': member.pk,")]
    patches['programs/models.py'] = [(
        "        return [(name.replace('_', ' ').capitalize(), {side: readable(value) for side, value in change.items()})\n                for name, change in self.changes.items()]",
        "        changes = self.changes if isinstance(self.changes, dict) else {'details': self.changes}\n        return [(str(name).replace('_', ' ').capitalize(),\n                 {side: readable(value) for side, value in\n                  (change if isinstance(change, dict) and ('before' in change or 'after' in change)\n                   else {'before': '', 'after': change}).items()})\n                for name, change in changes.items()]")]
    patches['programs/review_context.py'] = [(
        '    return context',
        "    from program_intake.presentation import update_review_context\n    return update_review_context(context, application, case)")]
    patches['ewaf/test_decision_migrations.py'] = [(
        '        old_models = [model for model in apps.get_models() if model not in (Decision, Audit, OperationalConfiguration, OperationalRun, OperationalDecision)]',
        "        from program_intake.migration_test_support import surviving_models\n        old_models = surviving_models(('ewaf', '0006_source_invalidation_foundation'))")]
    patches['ewaf/test_generation_migrations.py'] = [(
        "        old_models = [model for model in apps.get_models() if model not in FOUNDATION_MODELS and\n                      model not in (DevelopmentHumanDecision, DevelopmentHumanDecisionAudit, OperationalConfiguration, OperationalRun, OperationalDecision)]",
        "        from program_intake.migration_test_support import surviving_models\n        old_models = surviving_models(('ewaf', '0005_durable_development'))"), (
        "            with connection.execute_wrapper(read_only):\n                Command(stdout=output).check_migrations()\n            self.assertIn('remain unapplied as intended', output.getvalue())",
        "            from django.core.management.base import CommandError\n            with connection.execute_wrapper(read_only), self.assertRaisesMessage(CommandError, 'program_intake.0001_initial'):\n                Command(stdout=output).check_migrations()")]
    patches['core/test_local_startup.py'] = [(
        "            with connection.execute_wrapper(read_only):\n                Command(stdout=output).check_migrations()\n            self.assertIn('Annual observance setup is pending', output.getvalue())\n            self.assertIn('Live EWAF processing remains disabled', output.getvalue())",
        "            with connection.execute_wrapper(read_only), self.assertRaisesMessage(CommandError, 'program_intake.0001_initial'):\n                Command(stdout=output).check_migrations()"), (
        "            with connection.execute_wrapper(read_only):\n                command.check_migrations()\n            self.assertIn('remain unapplied as intended', output.getvalue())",
        "            with connection.execute_wrapper(read_only), self.assertRaisesMessage(CommandError, 'program_intake.0001_initial'):\n                command.check_migrations()")]
    for name, changes in patches.items():
        path = RUNTIME / name
        original = BACKUP / name
        if not original.exists():
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, original)
        content = original.read_text(encoding='utf-8')
        for old, new in changes:
            content = replace(content, old, new)
        if name == 'ewaf/test_generation_migrations.py':
            content = content.replace("WHERE NOT (app='ewaf'", "WHERE app <> 'program_intake' AND NOT (app='ewaf'")
        if name == 'core/test_local_startup.py':
            old = "                call_command('runlocal', '127.0.0.1:8000', use_reloader=False, stdout=StringIO())\n                serve.assert_called_once()"
            assert content.count(old) == 2
            content = content.replace(old, "                with self.assertRaisesMessage(CommandError, 'program_intake.0001_initial'):\n                    call_command('runlocal', '127.0.0.1:8000', use_reloader=False, stdout=StringIO())\n                serve.assert_not_called()")
        if path.suffix == '.py':
            compile(content, str(path), 'exec')
        path.write_text(content, encoding='utf-8', newline='\n')
    print('Installed program-intake hooks in the isolated port-8000 runtime only.', flush=True)


if __name__ == '__main__':
    install()
