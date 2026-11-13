"""Operational four-criterion policy, complete-pool calculation and human review."""
from contextlib import contextmanager
from datetime import timezone as datetime_timezone
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from programs.terms import terms_lock
from .evidence import VIEW as EVIDENCE_VIEW, approval_context, canonical, digest, source_context
from .evidence_services import persist, reasoned
from .models import EvidencePolicyRevision, CriterionAssessment
from .operational_models import OperationalConfiguration as Configuration, OperationalRun as Run, OperationalDecision as Decision
from . import operational_policy as policy
from .operational_policy import ahp
from .four_pool import eligibility
from .generation_inputs import lock_sources
from .readiness import evaluate, ineligible_exclusion_errors
from .source_freshness import observe
from .workspace_read_cache import reuse_inventory

VIEW = (*EVIDENCE_VIEW, 'ewaf.view_operational')


def available():
    """Schema metadata only; normal startup never migrates or activates policies."""
    tables = set(connection.introspection.table_names())
    return all(model._meta.db_table in tables for model in (Configuration, Run, Decision))


def actor(user, permission=None):
    current = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if current is None:
        raise PermissionDenied
    require_workspace_permissions(current, *VIEW, *([permission] if permission else []))
    return current


@contextmanager
def fence(program_id, user, permission=None):
    with terms_lock():
        current = actor(user, permission)
        authority = (current.pk, current.is_superuser, frozenset(current.get_all_permissions()))
        program = Program.objects.select_for_update().get(pk=program_id)
        applications = lock_sources(program, maximum=policy.MAX_POOL)
        yield current, program, applications
        final = actor(user, permission)
        if authority != (final.pk, final.is_superuser, frozenset(final.get_all_permissions())):
            raise PermissionDenied('Administrator authority changed. Reload before continuing.')


def configuration_source(program):
    evidence = EvidencePolicyRevision.objects.filter(program=program).first()
    # New configurations can be locked before publication. Bind actual approved
    # terms instead of the publication counter; historical sources stay exact.
    previous = Configuration.objects.filter(program=program).first()
    if previous and previous.uses_dataset_scoring:
        from .revised.live_services import dataset_source
        return dataset_source(program)
    from programs.application_workflow import enabled
    if ((previous and previous.source.get('contract') == 'approved_program_terms_v2')
            or (not previous and enabled())):
        from programs.terms import snapshot_terms, terms_digest
        return canonical({'contract': 'approved_program_terms_v2',
            'program_terms_digest': terms_digest(snapshot_terms(program)),
            'policy_authorized_at': program.policy_authorized_at,
            'policy_authorized_by': program.policy_authorized_by_id,
            'approval': approval_context(program), 'evidence_policy': evidence.pk if evidence else None,
            'evidence_digest': evidence.digest if evidence else None})
    return canonical({'program_version': program.version, 'approval': approval_context(program),
                      'evidence_policy': evidence.pk if evidence else None,
                      'evidence_digest': evidence.digest if evidence else None})


def configuration_token(program):
    latest = Configuration.objects.filter(program=program).first()
    return digest({'source': configuration_source(program), 'latest': latest.digest if latest else None})


def latest_configuration(program, *, require_locked=True):
    row = Configuration.objects.filter(program=program).first()
    if not row:
        raise ValidationError('configuration: no program-specific scoring configuration has been recorded')
    row.clean()
    if row.uses_dataset_scoring:
        if require_locked:
            from .revised.live_services import require_binding
            require_binding(row)
        return row
    if require_locked:
        if row.status != 'LOCKED':
            raise ValidationError(['configuration: the latest version must be authorized and locked',
                                   *policy.findings(row.policy, row.judgments)])
        if row.source != configuration_source(program):
            raise ValidationError('configuration: terms or evidence policy changed; authorize a new version')
        now = timezone.now()
        if not parse_datetime(row.policy['effective_from']) <= now < parse_datetime(row.policy['effective_until']):
            raise ValidationError('configuration.effective_from / effective_until: policy is not currently effective')
    return row


def record_configuration(program_id, *, user, expected, proposed, judgments, status, reason, attested=False):
    from .vault_policy import enabled as vault_enabled
    if vault_enabled():
        raise ValidationError('Edit shared weights and scoring rules in the EWAF Configuration Vault.')
    permission = 'ewaf.authorize_operational' if status == 'LOCKED' else 'ewaf.configure_operational'
    with fence(program_id, user, permission) as (current, program, applications):
        from .shared_weights import publication_locked
        if publication_locked(program):
            raise ValidationError('Weights are locked after program results are published. Programs without published results can use different Vault weights.')
        if Configuration.objects.filter(program=program, dataset_policy__isnull=False).exists():
            raise ValidationError('Use the explicit dataset-policy binding service for this program.')
        if status not in ('DRAFT', 'LOCKED') or expected != configuration_token(program):
            raise ValidationError('Configuration changed. Reload the current version before saving.')
        fields = reasoned(current, reason, True)
        if len(str(proposed)) > 64000 or len(str(judgments)) > 2000 or not isinstance(proposed, dict):
            raise ValidationError('Configuration is too large or invalid.')
        from .weight_input import validate_provenance
        validate_provenance(proposed.get('weight_input'), judgments)
        source = configuration_source(program)
        evidence = EvidencePolicyRevision.objects.filter(pk=source['evidence_policy']).first()
        validation = {}
        try:
            validation = ahp(judgments)
        except ValidationError:
            pass
        if status == 'LOCKED':
            if attested is not True:
                raise ValidationError('Explicit verification of the recorded Association authority is required.')
            policy.validate(proposed, judgments)
            if not evidence:
                raise ValidationError('evidence_policy: record the program evidence definitions first')
            evidence.clean()
            if program.slots is None or program.slots < 1:
                raise ValidationError('program.slots: approved positive beneficiary capacity required')
            if not program.ewaf_applicable or not program.policy_authorized_at:
                raise ValidationError('program: authorized EWAF selection policy required')
            from programs.approval_policy import binding_condition
            if not Program.objects.filter(pk=program.pk).filter(binding_condition()).exists():
                raise ValidationError('program: current approved terms binding required')
            if source['approval']['terms_digest'] != source['approval']['actual_terms_digest']:
                raise ValidationError('program: approved terms have changed')
            if evidence.terms_digest != source['approval']['terms_digest']:
                raise ValidationError('evidence_policy: definitions must bind the current approved terms')
            rubric = evidence.snapshot['criteria']['PR'].get('rubric_definition') or {}
            indexed = {item['id']: item for item in rubric.get('items', [])}
            used = []
            for role, gate in proposed['eligibility'].items():
                if gate['item'] not in indexed or gate['accepted_outcome'] not in indexed[gate['item']]['outcomes']:
                    raise ValidationError('PR.' + role + ': choose a documented rubric item and outcome')
                used.append(gate['item'])
            if len(set(used)) != 3:
                raise ValidationError('PR: functional need, consent and accessible alternatives require distinct evidence items')
            for code, rule in proposed['criteria'].items():
                defined = evidence.snapshot['criteria'].get(code, {})
                if rule['source_type'] not in defined.get('source_types', []) or rule['unit'] != defined.get('unit'):
                    raise ValidationError(code + ': scoring source and unit must match the verified evidence policy')
            if proposed['criteria']['PA']['source_type'] != 'successful_releases' or proposed['criteria']['PA']['unit'] != 'records':
                raise ValidationError('PA: supported measurement is the verified successful-release ledger count')
        previous = Configuration.objects.filter(program=program).first()
        return persist(Configuration(program=program, previous=previous, revision=previous.revision + 1 if previous else 1,
            status=status, policy=proposed, judgments=judgments, validation=validation, source=source,
            evidence_policy=evidence, **fields))


def _observation(program, applications, user):
    result = observe(program, applications, user)
    # Read authority afresh at each operation; a calculation is shared by authorized officers.
    result.pop('authority_digest')
    from programs.models import ProgramLog
    result['program_events'] = list(ProgramLog.objects.filter(program=program)
        .exclude(action__startswith='durable_').exclude(action__startswith='g12_operational')
        .exclude(action__in=['photo_viewed', 'document_downloaded']).order_by('pk').values_list('pk', flat=True))
    # Opening a protected profile/photo appends an access audit, not new evidence.
    # Retain these audits, but use only source-changing events for operational
    # freshness. File bytes, verification revisions and profile versions remain
    # independently captured and checked. Historical development observe() stays
    # unchanged.
    from members.models import MemberEvent
    from membership.models import MembershipEvent
    result['member_events'] = list(MemberEvent.objects.filter(member_id__in={app.member_id for app in applications})
        .exclude(action='document_downloaded').order_by('pk').values_list('pk', flat=True))
    result['membership_events'] = list(MembershipEvent.objects.filter(application_id__in={app.member.application_id for app in applications})
        .exclude(action='document_downloaded').order_by('pk').values_list('pk', flat=True))
    # Native reference edits have no numeric generation outside the preserved
    # development protocol. Retain their audited transitions as well as current
    # values, so a changed-and-restored reference cannot revive an old result.
    from django.contrib.admin.models import LogEntry
    from django.db.models import Q
    reference_types = (('documents', 'documenttype'), ('documents', 'membershipdocumentrequirement'),
                       ('members', 'disabilitytype'), ('membership', 'membershipsettings'))
    scope = Q(pk__in=[])
    for app, model in reference_types:
        scope |= Q(content_type__app_label=app, content_type__model=model)
    result['reference_audits'] = digest(list(LogEntry.objects.filter(scope).order_by('pk').values(
        'pk', 'user_id', 'content_type_id', 'object_id', 'action_flag', 'change_message')))
    return result


@reuse_inventory
def inventory(program, applications, configuration=None):
    if configuration and configuration.uses_dataset_scoring:
        from .revised.live_evidence import inventory as dataset_inventory
        return dataset_inventory(program, applications, configuration)
    if configuration and configuration.vault_revision_id:
        from .vault_sources import inventory as registered_inventory
        return registered_inventory(program, applications, configuration)
    rows, accepted, problems = [], {}, []
    for application in applications:
        source = source_context(application)
        ready = evaluate(application, context=source)
        errors = [item['code'] for group in ('eligibility', 'criteria') for item in ready['reasons'][group]]
        errors += [item['code'] for item in ready['reasons']['governance'] if item['code'] != 'CRITERION_POLICY_UNAPPROVED']
        gate, inputs, assessments = None, {}, {}
        if application.status == 'INELIGIBLE':
            errors = ineligible_exclusion_errors(source)
        elif application.status != 'ELIGIBLE':
            errors.append('APPLICATION_REVIEW_UNRESOLVED')
        elif configuration:
            try:
                pr = CriterionAssessment.objects.filter(application=application, criterion='PR').first()
                if not pr or pr.policy_id != configuration.evidence_policy_id:
                    raise ValidationError('PR: current verified functional-need assessment required')
                pr.clean()
                gate = eligibility(pr, configuration.policy['eligibility'])
                for code in policy.criteria_for(configuration.policy):
                    assessment = CriterionAssessment.objects.filter(application=application, criterion=code).first()
                    rule = configuration.policy['criteria'][code]
                    if not assessment or assessment.policy_id != configuration.evidence_policy_id:
                        raise ValidationError(code + ': current verified assessment required')
                    assessment.clean()
                    if any(getattr(assessment, key) != rule[key] for key in ('source_type', 'unit', 'value_type')):
                        raise ValidationError(code + ': assessment measurement does not match the locked policy')
                    value = assessment.value
                    if code == 'PA':
                        releases = source['pa']['successful']
                        if configuration.policy['pa_scope'] == 'this_program':
                            ids = set(str(pk) for pk in ProgramApplication.objects.filter(program=program).values_list('pk', flat=True))
                            releases = [r for r in releases if r['application_id'] in ids]
                        if configuration.policy['pa_period'] == 'date_range':
                            releases = [r for r in releases if configuration.policy['pa_start'] <= r['released_on'] <= configuration.policy['pa_end']]
                        value = len(releases)
                    inputs[code] = {'source_type': assessment.source_type, 'unit': assessment.unit, 'value': value}
                    assessments[code] = {'id': assessment.pk, 'digest': assessment.digest, 'payload': assessment.payload()}
            except (ValidationError, KeyError) as error:
                errors.extend(error.messages if isinstance(error, ValidationError) else ['configuration: missing criterion settings'])
        if application.status != 'INELIGIBLE' and application.submitted_at > program.registration_closes_at:
            errors.append('APPLICATION_SUBMITTED_AFTER_APPROVED_CLOSE: authorized review required')
        rows.append({'application': str(application.pk), 'reference': application.public_reference,
                     'status': application.status, 'errors': sorted(set(errors)), 'source': source,
                     'membership': ready['eligibility_readiness'], 'evidence': ready['criterion_completeness'], 'pr': bool(gate)})
        if errors:
            problems.extend(str(application.pk) + ': ' + error for error in sorted(set(errors)))
        elif application.status == 'ELIGIBLE' and configuration:
            accepted[str(application.pk)] = {'inputs': inputs, 'assessments': assessments, 'pr': gate}
    return rows, accepted, problems


def capture(program, applications, configuration, user, *, assessed_at=None):
    from .revised import rolling_pool
    if latest_configuration(program).pk != configuration.pk:
        raise ValidationError('configuration: a newer policy version exists')
    rolling = rolling_pool.enabled(configuration.policy)
    if not rolling and program.registration_closes_at > timezone.now():
        raise ValidationError('program.registration_closes_at: complete-pool scoring starts after the application period closes')
    if configuration.uses_dataset_scoring:
        from .revised.live_services import require_scoring_enabled
        require_scoring_enabled()
        if not rolling and timezone.now() < configuration.assessment_cutoff:
            raise ValidationError('The bound assessment cutoff has not occurred.')
    runtime, window = (rolling_pool.assessment_configuration(configuration, assessed_at)
                       if rolling else (configuration, None))
    before = _observation(program, applications, user)
    from . import employment_scoring
    runtime = employment_scoring.runtime(runtime)
    rows, accepted, problems = inventory(program, applications, runtime)
    if problems:
        raise ValidationError(problems)
    if not accepted:
        raise ValidationError('eligible_pool: at least one fully verified eligible application is required')
    employment_rule = employment_scoring.capture(configuration)
    if employment_rule and any(row['inputs']['ES']['value'] not in employment_scoring.SCORES for row in accepted.values()):
        raise ValidationError('Review employment using Employed, Self-Employed, Student, Retired or Unemployed before generating a new ranking. Saved earlier rankings keep their original scores.')
    after = _observation(program, applications, user)
    if before != after:
        raise ValidationError('Sources changed during review. Reload before calculating.')
    from .shared_weights import capture as capture_weights
    from .shared_calculation_rules import capture as capture_rules
    from .household_scoring import capture as capture_household
    contract = {}
    from .dataset_methods import is_composite
    if configuration.uses_dataset_scoring and is_composite(configuration.policy):
        from .revised.fulfillment import CONTRACT
        contract = {'assessment_source_contract': CONTRACT}
    return canonical({'engine': policy.engine_for(configuration.policy), 'program': str(program.pk), 'configuration_digest': configuration.digest,
        'manifest': rows, 'eligible': accepted, 'observation': after, 'evaluation_date': str(timezone.localdate()),
        'timezone': timezone.get_current_timezone_name(), **capture_weights(configuration), **capture_rules(configuration), **contract,
        **employment_rule, **capture_household(configuration), **({rolling_pool.KEY: window} if rolling else {})})


def context(program_id, *, user):
    from .revised.rolling_pool import observation
    with fence(program_id, user) as (current, program, applications):
        configuration = latest_configuration(program)
        snapshot = capture(program, applications, configuration, current)
        previous = Run.objects.filter(program=program).first()
        return {'source': digest(observation(snapshot)), 'previous': previous.pk if previous else None,
                'configuration': configuration.pk}


def generate(program_id, *, user, expected, reason, request_key):
    from .revised.rolling_pool import observation, observed_at
    with fence(program_id, user, 'ewaf.calculate_operational') as (current, program, applications):
        fields = reasoned(current, reason, True)
        try:
            request_key = UUID(str(request_key))
        except (ValueError, TypeError):
            raise ValidationError('Calculation request identifier is invalid.')
        configuration = latest_configuration(program)
        previous = Run.objects.filter(program=program).first()
        existing = Run.objects.filter(program=program, request_key=request_key).first()
        snapshot = capture(program, applications, configuration, current,
                           assessed_at=observed_at(existing.snapshot) if existing else None)
        if existing:
            if existing.pk != (previous.pk if previous else None) or existing.snapshot != snapshot or existing.reason != fields['reason'] or existing.actor_id != current.pk or expected != {'source': digest(observation(snapshot)), 'previous': existing.previous_id, 'configuration': configuration.pk}:
                raise ValidationError('Calculation retry conflicts with retained history.')
            existing.clean()
            return existing
        if expected != {'source': digest(observation(snapshot)), 'previous': previous.pk if previous else None, 'configuration': configuration.pk}:
            raise ValidationError('Calculation sources or predecessor changed. Reload before generating.')
        # The authorized policy sets the hard deadline. Each use independently
        # re-evaluates dated evidence and current program authority; an arbitrary
        # daily development-session expiration is not an Association rule.
        until = parse_datetime(configuration.policy['effective_until']).astimezone(datetime_timezone.utc)
        from .shared_calculation_rules import KEY as RULES_KEY
        if RULES_KEY in snapshot:
            until = min(until, parse_datetime(snapshot[RULES_KEY]['effective_until']))
        row = persist(Run(program=program, configuration=configuration, previous=previous,
            revision=previous.revision + 1 if previous else 1, request_key=request_key,
            snapshot=snapshot, calculations=policy.calculations(snapshot, configuration), valid_until=until, **fields))
        if capture(program, applications, configuration, current, assessed_at=observed_at(snapshot)) != snapshot or timezone.now() >= until:
            raise ValidationError('Sources changed or evidence expired before calculation commit.')
        return row


def _current(program, applications, user, run_id=None):
    run = Run.objects.filter(program=program).first()
    if not run or run_id is not None and run.pk != run_id:
        raise ValidationError('calculation: generate or open the current complete-pool calculation')
    run.clean()
    if timezone.now() >= run.valid_until:
        raise ValidationError('calculation: evidence or policy validity expired; review and recalculate')
    from .revised.rolling_pool import observed_at
    observed = capture(program, applications, run.configuration, user, assessed_at=observed_at(run.snapshot))
    from .employment_scoring import KEY as EMPLOYMENT_KEY
    if observed.get(EMPLOYMENT_KEY) != run.snapshot.get(EMPLOYMENT_KEY):
        raise ValidationError('Employment scoring changed to the five-category rule. Generate a new ranking before further decisions; the saved ranking keeps its original scores.')
    from .household_scoring import require_current as require_household
    require_household(run.configuration, run.snapshot)
    from .shared_weights import KEY
    if observed.get(KEY) != run.snapshot.get(KEY):
        raise ValidationError('The approved Vault weights changed. Generate a new EWAF ranking before making further decisions. This saved calculation retains its original weights.')
    from .shared_calculation_rules import KEY as RULES_KEY
    if observed.get(RULES_KEY) != run.snapshot.get(RULES_KEY):
        raise ValidationError('The approved equal-value calculation rule changed. Generate a new EWAF ranking. This saved calculation retains its original contributions.')
    # Evaluation date is retained as provenance, not a substitute source change.
    # evaluate() above still checks every actual evidence expiry at today's date.
    from .ranking_freshness import matches
    unchanged, rechecks = matches(run, observed)
    if not unchanged:
        raise ValidationError('calculation: verified sources changed; review corrections and recalculate')
    run.eligibility_rechecks = rechecks
    return run


def latest_decisions(program):
    latest = Decision.objects.filter(program=program, application_id=OuterRef('application_id')).order_by('-revision').values('pk')[:1]
    return Decision.objects.filter(program=program, pk=Subquery(latest)).select_related('run')


def record_decision(program_id, *, user, run_id, application_id, expected_revision, outcome, reason, tie_reason=''):
    with fence(program_id, user, 'ewaf.decide_operational') as (current, program, applications):
        require_workspace_permissions(current, 'assistance.decide_assistance')
        fields = reasoned(current, reason, True)
        if type(expected_revision) is not int or outcome not in ('SELECTED', 'NOT_SELECTED', 'DEFERRED'):
            raise ValidationError('A supported decision and revision are required.')
        run = current_result_run(program, applications, current, run_id)
        from .revised import rolling_pool
        if rolling_pool.selection_waiting(run.snapshot, run.configuration):
            raise ValidationError('Generate a final ranking after registration closes and the assessment cutoff is reached before selecting beneficiaries.')
        application = next((app for app in applications if str(app.pk) == str(application_id)), None)
        if not application or str(application.pk) not in run.calculations:
            raise ValidationError('Choose an eligible application in the current calculation.')
        from assistance.models import AssistanceRelease
        if AssistanceRelease.objects.filter(application=application, voided_at__isnull=True).exists():
            raise ValidationError('Actual assistance is already recorded; use the authorized release review procedure.')
        previous = Decision.objects.filter(application=application).order_by('-revision').first()
        if expected_revision != (previous.revision if previous else 0):
            if previous and previous.run_id == run.pk and previous.outcome == outcome and previous.reason == fields['reason'] and previous.tie_reason == tie_reason and previous.actor_id == current.pk and previous.revision == expected_revision + 1:
                previous.clean()
                return previous
            raise ValidationError('Decision changed. Reload the latest human decision before saving.')
        compared = run.calculations[str(application.pk)]['comparison']
        tied = compared['equal'] > 1
        if run.configuration.uses_dataset_scoring:
            tied = compared['capacity_boundary_tie']
        if outcome in ('SELECTED', 'NOT_SELECTED') and tied:
            if run.configuration.policy['tie_rule'] in ('hold', 'hold_boundary'):
                raise ValidationError('tie_rule: this authorized policy holds exact ties for further review')
            if not isinstance(tie_reason, str) or not tie_reason.strip() or len(tie_reason) > 2000:
                raise ValidationError('tie_reason: explain how the authorized tie procedure was applied')
        choices = list(latest_decisions(program))
        for choice in choices:
            choice.clean()
        from programs.mandatory_ewaf import retained_selected_ids
        selected_ids = retained_selected_ids(program)
        selected_ids.update(row.application_id for row in choices if row.outcome == 'SELECTED')
        selected = len(selected_ids - {application.pk})
        if outcome == 'SELECTED' and (program.slots is None or selected >= program.slots):
            raise ValidationError('program.slots: all approved beneficiary slots are reserved')
        row = persist(Decision(program=program, application=application, run=run, previous=previous,
            revision=expected_revision + 1, outcome=outcome, tie_reason=tie_reason.strip(),
            review={'run_digest': run.digest, 'configuration_digest': run.configuration.digest,
                    'score': run.calculations[str(application.pk)], 'slots': program.slots,
                    'tie_rule': run.configuration.policy['tie_rule'],
                    # Fixed scoring holds boundary ties through tie_rule; it has
                    # no separate discretionary tie-procedure text to copy.
                    'tie_procedure': run.configuration.policy.get('tie_procedure', ''),
                    **({'selection_timing': {'rule': rolling_pool.SELECTION_RULE,
                         'registration_open': timezone.now() < program.registration_closes_at,
                         'ranking_window': run.snapshot[rolling_pool.KEY]}}
                       if rolling_pool.enabled(run.configuration.policy) else {}),
                    **({'eligibility_rechecks': run.eligibility_rechecks}
                       if getattr(run, 'eligibility_rechecks', None) else {})}, **fields))
        current_result_run(program, applications, current, run.pk)
        return row


def unselect_assistance(program_id, *, user, run_id, application_id, expected_revision):
    """Withdraw a selection without deleting history or making a new award.

    A changed scoring source need not prevent withdrawing an existing selection.
    Reselection still uses record_decision's full current-ranking validation.
    """
    from copy import deepcopy
    from assistance.models import AssistanceRelease
    with fence(program_id, user, 'ewaf.decide_operational') as (current, program, applications):
        require_workspace_permissions(current, 'assistance.decide_assistance')
        fields = reasoned(current, 'Administrator unselected this applicant for assistance.', True)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValidationError('Reload the selected applicant before unselecting.')
        application = next((app for app in applications if str(app.pk) == str(application_id)), None)
        if not application:
            raise ValidationError('Choose an applicant from this program.')
        previous = Decision.objects.filter(application=application).select_related('run__configuration', 'previous').order_by('-revision').first()
        if not previous or previous.run_id != run_id:
            raise ValidationError('Selection changed. Reload the selected applicant before unselecting.')
        previous.clean()
        previous.run.clean()
        if AssistanceRelease.objects.filter(application=application, voided_at__isnull=True).exists():
            raise ValidationError('Actual assistance is already recorded; use the authorized release review procedure.')
        if (previous.outcome == 'DEFERRED' and previous.review.get('selection_action') == 'unselected'
                and previous.actor_id == current.pk and previous.revision == expected_revision + 1
                and previous.previous and previous.previous.outcome == 'SELECTED'):
            return previous
        if previous.revision != expected_revision:
            raise ValidationError('Decision changed. Reload the latest human decision before saving.')
        if previous.outcome != 'SELECTED':
            raise ValidationError('This applicant is not selected for assistance.')
        review = deepcopy(previous.review)
        review.update(selection_action='unselected', selection_reversed=previous.pk)
        return persist(Decision(program=program, application=application, run=previous.run,
            previous=previous, revision=previous.revision + 1, outcome='DEFERRED',
            tie_reason='', review=review, **fields))


def ordered(run):
    if run.configuration.uses_dataset_scoring:
        from fractions import Fraction
        return sorted(({'application': key, **row} for key, row in run.calculations.items()),
                      key=lambda row: Fraction(row['score_exact']), reverse=True)
    return sorted(({'application': key, **row} for key, row in run.calculations.items()),
                  key=lambda row: Decimal(row['score_0_1']), reverse=True)


def delivery_decision_problem(run, decision):
    """Shared, read-only selection check for receipt pages and the release writer."""
    if not run or not decision:
        return 'Review the latest EWAF ranking and record a Selected beneficiary decision before recording receipt.'
    if decision.run_id != run.pk:
        return ('This beneficiary selection belongs to an earlier EWAF calculation. '
                'Review the latest ranking and confirm the beneficiary selection before recording receipt.')
    if decision.outcome != 'SELECTED':
        return 'The latest EWAF decision is not Selected. Review the beneficiary decision before recording receipt.'
    return ''


def delivery_selection(application, program, user):
    """Validate a saved selection for fulfillment, retaining its original ranking.

    Receipts from this same run are fulfillment of its decisions, not new scoring
    inputs for that already selected cohort. Every other source change still blocks
    delivery. Composite rerankings retain validated cutoff inputs and later receipts.
    Caller holds the program/terms transaction and records the receipt atomically.
    """
    from assistance.models import AssistanceRelease, AssistanceLog
    from copy import deepcopy
    if not available():
        raise ValidationError('Complete EWAF calculation and beneficiary selection before release.')
    run = Run.objects.filter(program=program).first()
    decision = Decision.objects.filter(application=application).first()
    problem = delivery_decision_problem(run, decision)
    if problem:
        raise ValidationError(problem)
    run.clean()
    decision.clean()
    if run.configuration.uses_dataset_scoring:
        from .revised.live_services import require_scoring_enabled
        require_scoring_enabled()
    if latest_configuration(program).pk != run.configuration_id or timezone.now() >= run.valid_until:
        raise ValidationError('The selected EWAF configuration expired or changed. Review the selection before release.')
    applications = lock_sources(program, maximum=policy.MAX_POOL)
    from .revised.fulfillment import CONTRACT
    if run.snapshot.get('assessment_source_contract') == CONTRACT:
        _current(program, applications, user, run.pk)
        selected = list(latest_decisions(program).filter(outcome='SELECTED'))
        if program.slots is None or len(selected) > program.slots:
            raise ValidationError('Beneficiary decisions exceed the program slots.')
        return decision
    from .ranking_freshness import comparable_observation
    if (comparable_observation(_observation(program, applications, user), program.pk)
            != comparable_observation(run.snapshot['observation'], program.pk)):
        raise ValidationError('Program sources changed after ranking. Review the affected pool before release.')
    manifest = {row['application']: row for row in run.snapshot['manifest']}
    selected = list(latest_decisions(program).filter(outcome='SELECTED'))
    if program.slots is None or len(selected) > program.slots:
        raise ValidationError('Beneficiary decisions exceed the program slots.')
    for item in applications:
        original = manifest.get(str(item.pk), {}).get('source')
        current = deepcopy(source_context(item))
        if run.configuration.uses_dataset_scoring:
            from .revised.live_evidence import context as dataset_context
            current = deepcopy(dataset_context(item))
        if not original:
            raise ValidationError('The ranked applicant pool changed.')
        receipt = AssistanceRelease.objects.successful().filter(application=item).first()
        if receipt:
            approval = receipt.approval_snapshot
            chosen = Decision.objects.filter(application=item).first()
            log = AssistanceLog.objects.filter(application=item, action='assistance_released').first()
            if (not chosen or chosen.run_id != run.pk or chosen.outcome != 'SELECTED'
                    or approval.get('operational_run_id') != run.pk
                    or approval.get('operational_decision_id') != chosen.pk
                    or not log or log.snapshot.get('release') != str(receipt.pk)
                    or log.snapshot.get('approval') != approval
                    or log.actor_id != receipt.recorded_by_id
                    or item.status != 'COMPLETED'
                    or item.version != original['application_version'] + 1):
                raise ValidationError('A completed receipt no longer matches its retained beneficiary approval.')
            chosen.clean()
            releases = list(AssistanceRelease.objects.filter(application__member_id=item.member_id)
                .exclude(pk=receipt.pk).order_by('pk').values(
                    'id', 'application_id', 'active_application_id', 'released_on', 'recorded_at',
                    'recorded_by_id', 'assistance_type', 'voided_at', 'voided_by_id'))
            current['pa'] = {
                'scope': current['pa']['scope'],
                'successful': canonical([row for row in releases if row['voided_at'] is None]),
                'all_release_state_digest': digest(releases),
                'count': sum(row['voided_at'] is None for row in releases),
            }
            current['status'] = original['status']
            current['application_version'] = original['application_version']
        if current != original:
            raise ValidationError('Verified applicant information changed after ranking. Review before release.')
        if original['status'] == 'ELIGIBLE':
            if run.configuration.uses_dataset_scoring:
                from .revised.live_evidence import accepted
                from .vault_sources import eligibility_errors
                errors = eligibility_errors(item, current)
                accepted(item, run.configuration, current)
            elif run.configuration.vault_revision_id:
                from .vault_sources import eligibility_errors, accepted_review, sources
                errors = eligibility_errors(item, current)
                accepted_review(item, run.configuration, sources(item, run.configuration, current))
            else:
                readiness = evaluate(item, context=current)
                errors = [reason['code'] for group in ('eligibility', 'criteria', 'governance')
                          for reason in readiness['reasons'][group]
                          if reason['code'] != 'CRITERION_POLICY_UNAPPROVED']
            if errors:
                raise ValidationError(errors)
    return decision


def current_result_run(program, applications, user, run_id=None):
    """A confirmed delivery fulfills a selection; it does not unrank its member.

    Caller holds the program/source transaction. Composite captures validate the
    original receipt approval even after reranking. Older contracts retain their
    exact-run fulfillment checks.
    """
    from assistance.models import AssistanceRelease
    run = Run.objects.filter(program=program).first()
    if not run or run_id is not None and run.pk != run_id:
        raise ValidationError('Open the current complete EWAF ranking before reviewing results.')
    from .revised.fulfillment import CONTRACT
    if run.snapshot.get('assessment_source_contract') == CONTRACT:
        return _current(program, applications, user, run.pk)
    receipt = AssistanceRelease.objects.successful().filter(application__program=program).select_related('application').first()
    if receipt is None:
        return _current(program, applications, user, run.pk)
    run.clean()
    if {str(app.pk) for app in applications} != {row['application'] for row in run.snapshot['manifest']}:
        raise ValidationError('The ranked applicant pool changed. Review the applications before publication.')
    # This validator checks the whole pool, receipt/decision/run bindings, native
    # release audit, exact version transition, evidence, configuration and expiry.
    delivery_selection(receipt.application, program, user)
    from .shared_weights import capture as current_weights, KEY
    from .employment_scoring import capture as current_employment, KEY as EMPLOYMENT_KEY
    if current_employment(run.configuration).get(EMPLOYMENT_KEY) != run.snapshot.get(EMPLOYMENT_KEY):
        raise ValidationError('Employment scoring changed. Review a new ranking before publishing results.')
    from .household_scoring import require_current as require_household
    require_household(run.configuration, run.snapshot)
    if current_weights(run.configuration).get(KEY) != run.snapshot.get(KEY):
        raise ValidationError('The approved Vault weights changed. Review the ranking before publishing results.')
    from .shared_calculation_rules import capture as current_rules, KEY as RULES_KEY
    if current_rules(run.configuration).get(RULES_KEY) != run.snapshot.get(RULES_KEY):
        raise ValidationError('The approved equal-value calculation rule changed. Review the ranking before publishing results.')
    return run


def publication_snapshot(program):
    """Internal allowlisted projection used by existing explicit publication services.

    Public reads may revalidate the projection, but never receive private source data.
    No actor is inferred as a new publisher; the existing announcement permission checks
    remain responsible for preparation and publication.
    """
    from collections import Counter
    from announcements.results import mask_identity
    if not available():
        raise ValidationError('Operational EWAF schema is not installed.')
    with terms_lock():
        program = Program.objects.select_for_update().get(pk=program.pk)
        applications = lock_sources(program, maximum=policy.MAX_POOL)
        latest = Run.objects.filter(program=program).first()
        if not latest:
            raise ValidationError('Generate the complete EWAF pool before preparing results.')
        try:
            current = actor(latest.actor, 'ewaf.calculate_operational')
        except PermissionDenied as error:
            raise ValidationError('The calculation authority needs review before result publication.') from error
        run = current_result_run(program, applications, current, latest.pk)
        decisions = {str(row.application_id): row for row in latest_decisions(program)}
        from .revised.fulfillment import fulfilled_decisions
        fulfilled = fulfilled_decisions(program)
        rows, private = [], []
        for application in applications:
            key = str(application.pk)
            if key not in run.calculations:
                continue
            decision = decisions.get(key)
            if (not decision or decision.run_id != run.pk and key not in fulfilled
                    or decision.outcome not in ('SELECTED', 'NOT_SELECTED')):
                raise ValidationError('Finish every eligible application decision against the current calculation before publication.')
            decision.clean()
            try:
                author = actor(decision.actor, 'ewaf.decide_operational')
                require_workspace_permissions(author, 'assistance.decide_assistance')
            except PermissionDenied as error:
                raise ValidationError('A beneficiary decision authority needs review before result publication.') from error
            private.append([key, decision.digest])
            if decision.outcome == 'SELECTED':
                rows.append(mask_identity(application.member.full_name, application.public_reference))
        if program.slots is None or len(rows) > program.slots:
            raise ValidationError('Selected beneficiaries exceed approved slots.')
        rows.sort(key=lambda row: (row['name'], row['reference']))
        counts = Counter((row['name'], row['reference']) for row in rows)
        for row in rows:
            row['ambiguous'] = counts[(row['name'], row['reference'])] > 1
        payload = {'schema': 1, 'program_name': program.name, 'description': program.description,
            'program_date': timezone.localtime(program.starts_at).strftime('%B %d, %Y, %I:%M %p') if program.starts_at else 'Schedule to be announced',
            'slots': program.slots, 'eligible_count': len(run.calculations), 'selection_method': program.selection_method,
            'eligibility_explanation': 'Verified association membership, program requirements and documented functional need were reviewed before scoring.',
            'ewaf_explanation': ', '.join(run.configuration.policy['criteria']) + ' were calculated using the retained authorized EWAF configuration. Program Relevance was a mandatory eligibility requirement. Authorized officers made separate reasoned beneficiary decisions within approved slots.',
            'rows': rows}
        return payload, digest({'run': run.digest, 'decisions': private, 'public_payload': payload})
