"""Private operational EWAF pages in the existing Admin shell."""
from uuid import uuid4
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from programs.models import Program
from . import operational_services as service
from .operational_policy import findings, MAX_POOL, CRITERIA
from .household_criteria import criteria_for, LEGACY_CRITERIA
from .operational_models import OperationalConfiguration as Configuration, OperationalRun as Run, OperationalDecision as Decision
from .operational_forms import WeightConfigurationForm, GenerateForm, DecisionForm, SelectAssistanceForm, UnselectAssistanceForm
from .presentation import messages_for_officers, simplify_form_errors
from .workspace_read_cache import reuse_workspace_inventory


def shell(request, template, context, status=200):
    from django.conf import settings
    context['fictional'] = getattr(settings, 'EWAF_FICTIONAL_DEMO', False)
    context['compact_workspace_navigation'] = template in ('ewaf/operational_workspace.html', 'ewaf/score_breakdown.html')
    return render(request, template, context, status=status)


def schema_response(request):
    return shell(request, 'ewaf/operational_unavailable.html', {}, status=503)


@never_cache
@dashboard_required
@require_http_methods(['GET'])
def programs(request):
    service.actor(request.user)
    if not service.available():
        return schema_response(request)
    from .selection_workspace import workspace as selection_workspace
    return shell(request, 'ewaf/operational_programs.html', selection_workspace(request))


@never_cache
@dashboard_required
@require_http_methods(['GET'])
def retired_preview(request):
    service.actor(request.user)
    return redirect('ewaf:operational_programs')


@never_cache
@dashboard_required
@require_http_methods(['GET'])
@reuse_workspace_inventory
def selection_panel(request, pk):
    service.actor(request.user)
    if not service.available():
        return schema_response(request)
    from .program_cards import applicant_counts
    from .selection_workspace import panel
    program = get_object_or_404(applicant_counts(Program.objects.filter(ewaf_applicable=True)), pk=pk)
    return render(request, 'ewaf/selection/panel.html', panel(program, request.user))


@never_cache
@dashboard_required
@require_http_methods(['GET'])
def export_run(request, pk, run_id):
    """Private retained calculation; no live data substitution or public projection."""
    service.actor(request.user)
    run = get_object_or_404(Run.objects.select_related('configuration'), pk=run_id, program_id=pk)
    try:
        run.clean()
    except ValidationError:
        return JsonResponse({'errors': ['This retained calculation needs integrity review before it can be exported.']}, status=409)
    from .evidence import canonical
    payload = canonical({'method': run.snapshot['engine'], 'criteria': list(criteria_for(run.configuration.policy)),
        'program': str(pk), 'run_id': run.pk, 'revision': run.revision, 'digest': run.digest,
        'configuration': run.configuration.payload(), 'configuration_digest': run.configuration.digest,
        'snapshot': run.snapshot, 'calculations': run.calculations, 'recorded_at': run.recorded_at,
        'actor': run.actor_label, 'reason': run.reason, 'historical_snapshot': True})
    service.actor(request.user)
    response = JsonResponse(payload, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="ewaf-{pk}-run-{run.revision}.json"'
    response['Cache-Control'] = 'no-store, private'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def configuration(request, pk):
    service.actor(request.user)
    if not service.available():
        return schema_response(request)
    if request.method == 'GET':
        from django.urls import reverse
        return redirect(reverse('ewaf:operational_workspace', kwargs={'pk': pk}) + '#configuration')
    return workspace(request, pk)


def configuration_context(request, program, current):
    pk = program.pk
    latest = Configuration.objects.filter(program=program).first()
    if latest and latest.uses_dataset_scoring:
        if request.method == 'POST' and request.POST.get('action') in ('DRAFT', 'LOCKED', 'PREVIEW_WEIGHTS'):
            return JsonResponse({'errors': ['Use the versioned dataset-policy review and explicit program binding.']}, status=400)
        from .revised.live_services import require_binding
        from django.utils import timezone
        blockers = []
        try:
            require_binding(latest)
            from .shared_weights import current as current_weights
            shared_weights = current_weights(latest)
            from .shared_calculation_rules import current as current_rules
            shared_calculation_rules = current_rules(latest)
        except ValidationError as error:
            blockers = error.messages
            shared_weights = None
            shared_calculation_rules = None
        from .revised import rolling_pool
        rolling = rolling_pool.enabled(latest.policy)
        waiting = ('Calculation waits until the approved application closing time and assessment cutoff.'
                   if not rolling and timezone.now() < latest.assessment_cutoff else '')
        from .employment_scoring import SCORES
        return {'configuration': latest, 'can_configure': False, 'can_authorize': False,
                'fixed_scoring': bool(latest.policy.get('fixed_scoring_version')),
                'employment_scoring': SCORES.items(),
                'shared_weights': shared_weights,
                'shared_calculation_rules': shared_calculation_rules,
                'dataset_policy_ready': not blockers, 'dataset_policy_blockers': blockers, 'dataset_waiting': waiting,
                'ranking_during_registration': rolling and timezone.now() < program.registration_closes_at}
    from .vault_policy import enabled as vault_enabled
    if vault_enabled():
        if request.method == 'POST' and request.POST.get('action') in ('DRAFT', 'LOCKED', 'PREVIEW_WEIGHTS'):
            return JsonResponse({'errors': ['Configure shared weights and rules in the EWAF Configuration Vault.']}, status=400)
        from .revised.shared_application import status as shared_status
        return {'configuration': latest, 'can_configure': False, 'can_authorize': False,
                'shared_configuration': shared_status(program, latest)}
    from .weight_input import initial_state, preview
    if request.method == 'POST' and request.POST.get('action') == 'PREVIEW_WEIGHTS':
        if not (current.has_perm('ewaf.configure_operational') or current.has_perm('ewaf.authorize_operational')):
            raise PermissionDenied
        import json
        try:
            expected = service.configuration_token(program)
            if request.POST.get('expected') != expected:
                raise ValidationError('Configuration changed. Reload before reviewing a weight proposal.')
            proposal = json.loads(request.POST.get('slider_proposal', ''))
            return JsonResponse(preview(proposal, program=pk, expected=expected))
        except (ValidationError, ValueError) as error:
            return JsonResponse({'errors': error.messages if isinstance(error, ValidationError)
                                 else ['Invalid weight proposal.']}, status=400)
    configuring = request.method == 'POST' and request.POST.get('action') in ('DRAFT', 'LOCKED')
    upgrading_criteria = bool(latest and criteria_for(latest.policy) == LEGACY_CRITERIA and
        (request.method == 'GET' or request.POST.get('criteria_profile') == 'household_five'))
    editing_settings = request.GET.get('settings') == '1'
    if request.GET.get('settings') == '1' and not current.has_perm('ewaf.configure_operational'):
        raise PermissionDenied
    from .policy_forms import GuidedConfigurationForm
    form_class = GuidedConfigurationForm if editing_settings else WeightConfigurationForm
    form = form_class(request.POST if configuring else None, configuration=None if upgrading_criteria else latest, program=program,
        initial={'expected': service.configuration_token(program)})
    if configuring and form.is_valid():
        try:
            service.record_configuration(pk, user=current, expected=form.cleaned_data['expected'],
                proposed=form.proposed(), judgments=form.judgments(), status=request.POST.get('action'),
                reason=form.cleaned_data['reason'], attested=form.cleaned_data['attested'])
            from django.urls import reverse
            return redirect(reverse('ewaf:operational_workspace', kwargs={'pk': pk}) + '#configuration')
        except ValidationError as error:
            form.add_error(None, error)
    simplify_form_errors(form)
    missing = findings(latest.policy, latest.judgments) if latest else ['configuration: enter the Association-approved values; no defaults are supplied']
    math_rows = []
    if latest and latest.validation:
        from .weight_input import percentages
        units = percentages(latest.validation['weights'])
        from .policy_forms import NAMES
        for index, code in enumerate(criteria_for(latest.policy)):
            math_rows.append({'criterion': code, 'weight': latest.validation['weights'][code],
                'name': NAMES[code],
                'percent': f'{units[code] / 100:.2f}',
                'matrix': latest.validation['matrix'][index], 'normalized': latest.validation['normalized_matrix'][index]})
    weight_state = initial_state(None if upgrading_criteria else latest)
    if request.method == 'POST' and form.is_bound:
        try:
            import json
            from .weight_input import validate_proposal
            weight_state['proposal'] = validate_proposal(json.loads(form['slider_proposal'].value() or 'null'))
        except (ValidationError, ValueError, TypeError):
            pass
    return {'configuration': latest,
        'editing_settings': editing_settings, 'upgrading_criteria': upgrading_criteria,
        'weight_state': weight_state,
        'configuration_form': form, 'missing': missing, 'math_rows': math_rows,
        'configuration_history': Paginator(Configuration.objects.filter(program=program), 30).get_page(request.GET.get('configuration_page')),
        'can_configure': current.has_perm('ewaf.configure_operational'), 'can_authorize': current.has_perm('ewaf.authorize_operational')}


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
@reuse_workspace_inventory
def workspace(request, pk):
    current = service.actor(request.user)
    if not service.available():
        return schema_response(request)
    program = get_object_or_404(Program, pk=pk)
    if not program.ewaf_applicable:
        raise Http404
    configuration_data = configuration_context(request, program, current)
    if not isinstance(configuration_data, dict):
        return configuration_data
    configuration = Configuration.objects.filter(program=program).first()
    expected, problems, inventory, accepted_inputs = None, [], [], {}
    try:
        with service.fence(pk, current) as (current, program, applications):
            preview_configuration = configuration if configuration and configuration.status == 'LOCKED' else None
            from .revised import rolling_pool
            if preview_configuration and rolling_pool.enabled(preview_configuration.policy):
                preview_configuration, _ = rolling_pool.assessment_configuration(preview_configuration)
            from .employment_scoring import runtime as employment_runtime
            inventory, accepted_inputs, _ = service.inventory(program, applications, employment_runtime(preview_configuration))
        expected = service.context(pk, user=current)
    except ValidationError as error:
        problems = error.messages
    generating = request.method == 'POST' and request.POST.get('action') not in ('DRAFT', 'LOCKED', 'PREVIEW_WEIGHTS', 'DECISION', 'SELECT_ASSISTANCE', 'UNSELECT_ASSISTANCE')
    form = GenerateForm(request.POST if generating else None, auto_id='id_generate_%s',
        initial={'expected': expected, 'request_key': uuid4()})
    applications_by_id = {str(item.pk): item for item in program.applications.select_related('member')}
    if not inventory and applications_by_id:
        inventory = [{'application': str(item.pk), 'reference': item.public_reference,
                      'status': item.status, 'errors': []} for item in applications_by_id.values()]
    from .input_presentation import configuration_pending, input_details
    from .workspace_notices import mark_input_review, workspace_notice
    inputs_configuration_pending = configuration_pending(configuration)
    for item in inventory:
        application = applications_by_id[item['application']]
        item['member_name'] = application.member.full_name
        item['status_label'] = item['status'].replace('_', ' ').title()
        errors = item.get('errors', [])
        # A draft configuration has no input-review contract yet. Do not label
        # the legacy fallback's missing assessments as missing registration data.
        item['readiness_errors'] = messages_for_officers([
            error for error in errors if not (inputs_configuration_pending and error == 'CRITERION_MISSING')])
        item.update(input_details(application, configuration, accepted_inputs.get(item['application']),
                                  can_review=current.has_perm('ewaf.review_criterionassessment'), source=item.get('source')))
        mark_input_review(item)
    ready_count = sum(bool(item.get('evidence') and not item['errors']) for item in inventory)
    pending_count = sum(bool(item['errors']) for item in inventory)
    if generating and form.is_valid():
        try:
            run = service.generate(pk, user=current, reason=GenerateForm.audit_reason, **form.cleaned_data)
            from django.urls import reverse
            return redirect(reverse('ewaf:operational_workspace', kwargs={'pk': pk}) + '#results')
        except ValidationError as error:
            form.add_error(None, error)
    simplify_form_errors(form)
    latest_run = Run.objects.filter(program=program).first()
    selected_run = latest_run
    if request.GET.get('run'):
        try:
            selected_run = get_object_or_404(Run, program=program, pk=request.GET['run'])
        except (ValueError, ValidationError):
            raise Http404
    result_data = result_context(request, program, selected_run, current) if selected_run else {}
    if not isinstance(result_data, dict):
        return result_data
    inputs_by_id = {item['application']: item for item in inventory}
    for row in result_data.get('rows', []):
        details = inputs_by_id.get(row['application'], {})
        row['needs_review'] = details.get('needs_review', False)
        row['review_summary'] = details.get('review_summary', '')
    ranked_ids = set(selected_run.calculations) if selected_run and not result_data.get('invalid_calculation') else set()
    unranked = [item for item in inventory if item['application'] not in ranked_ids]
    query = request.GET.get('q', '').strip().casefold()
    if query:
        unranked = [item for item in unranked if query in ' '.join((item['member_name'], item['reference'])).casefold()]
    if result_data.get('decision_filter'):
        unranked = []
    unranked_page = Paginator(unranked, 50).get_page(request.GET.get('applicants_page'))
    requested_applicant = (request.POST.get('decision-application_id', '') if request.method == 'POST'
                           else request.GET.get('review', ''))
    if requested_applicant and requested_applicant not in applications_by_id:
        raise Http404
    selected_row = result_data.get('selected_row')
    selected_id = requested_applicant or (selected_row['application'] if selected_row else '')
    if not selected_id and unranked_page:
        selected_id = unranked_page[0]['application']
    selected_input = next((item for item in inventory if item['application'] == selected_id), None)
    for item in unranked_page:
        item['panel_selected'] = item['application'] == selected_id
    # Only the displayed pages are preloaded. Private cards stay in this page's
    # memory so a row switch does not inspect the entire applicant pool again.
    panel_rows = {row['application']: row for row in result_data.get('rows', [])}
    panel_ids = dict.fromkeys([*panel_rows, *(item['application'] for item in unranked_page)])
    default_applicant = next(iter(panel_ids), '')
    if selected_input:
        panel_ids[selected_id] = None
        if selected_row:
            panel_rows[selected_id] = selected_row
    applicant_panels = [{'application': key, 'input': inputs_by_id[key], 'row': panel_rows.get(key)}
                        for key in panel_ids if key in inputs_by_id]
    notice = workspace_notice(ready=expected is not None, result=result_data, inventory=inventory,
        configuration_pending=inputs_configuration_pending, missing=configuration_data.get('missing'), problems=problems)
    from programs.catalog import capacity_context
    capacity_context(program, current)
    return shell(request, 'ewaf/operational_workspace.html', {'program': program, **configuration_data,
        'result': result_data, 'applicant_count': program.applications.count(),
        'ready_count': ready_count, 'pending_count': pending_count,
        'inputs_configuration_pending': inputs_configuration_pending,
        'eligible_count': sum(item['status'] == 'ELIGIBLE' or item['application'] in accepted_inputs for item in inventory),
        'inventory': Paginator(inventory, 50).get_page(request.GET.get('applicants_page')),
        'selected_input': selected_input, 'unranked_applicants': unranked_page, 'workspace_notice': notice,
        'applicant_panels': applicant_panels, 'default_applicant': default_applicant,
        'problems': messages_for_officers(problems), 'ready': expected is not None, 'form': form,
        'can_calculate': current.has_perm('ewaf.calculate_operational'), 'limit': MAX_POOL,
        'latest_run': latest_run,
        'history': Paginator(Run.objects.filter(program=program).select_related('configuration'), 50).get_page(request.GET.get('history_page'))})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def result(request, pk, run_id):
    current = service.actor(request.user)
    if not service.available():
        return schema_response(request)
    program = get_object_or_404(Program, pk=pk)
    run = get_object_or_404(Run, program=program, pk=run_id)
    if request.method == 'GET':
        from django.urls import reverse
        query = request.GET.copy()
        query['run'] = str(run.pk)
        return redirect(reverse('ewaf:operational_workspace', kwargs={'pk': pk}) + '?' + query.urlencode() + '#results')
    request.POST = request.POST.copy()
    request.POST['action'] = 'DECISION'
    request.GET = request.GET.copy()
    request.GET['run'] = str(run.pk)
    return workspace(request, pk)


@never_cache
@dashboard_required
@require_http_methods(['GET'])
def breakdown(request, pk):
    template = 'ewaf/score_breakdown.html'
    current = service.actor(request.user)
    if not service.available():
        return schema_response(request)
    program = get_object_or_404(Program, pk=pk)
    if not program.ewaf_applicable:
        raise Http404
    runs = Run.objects.filter(program=program).select_related('configuration__evidence_policy', 'configuration__dataset_policy')
    run = runs.first()
    if request.GET.get('run'):
        try:
            run = get_object_or_404(runs, pk=int(request.GET['run']))
        except (ValueError, ValidationError):
            raise Http404
    context = {'program': program, 'run': run,
               'calculation_history': Run.objects.filter(program=program).values('pk', 'revision', 'recorded_at')}
    if run is None:
        return shell(request, template, context)
    try:
        run.clean()
    except ValidationError:
        return shell(request, template, {**context, 'invalid_calculation': True}, status=409)
    active, problems = False, []
    try:
        with service.fence(pk, current) as (current, program, applications):
            service.current_result_run(program, applications, current, run.pk)
        active = True
    except ValidationError as error:
        problems = error.messages
    from .score_breakdown import build_breakdown, calculation_guide
    members = {str(key): name for key, name in program.applications.values_list('pk', 'member__full_name')}
    rows = build_breakdown(run, members)
    from .workspace_ui import decorate_breakdown
    member_numbers = {str(key): number for key, number in program.applications.values_list('pk', 'member__control_number')}
    decorate_breakdown(run, rows, member_numbers)
    selected = rows[0] if rows else None
    if request.GET.get('applicant'):
        selected = next((row for row in rows if row['application'] == request.GET['applicant']), None)
        if selected is None:
            raise Http404
    selected_page = rows.index(selected) // 50 + 1 if selected else 1
    page = Paginator(rows, 50).get_page(request.GET.get('page', selected_page))
    service.actor(request.user)
    from .workspace_notices import workspace_notice
    return shell(request, template, {**context, 'selected': selected,
        'guide': calculation_guide(run, rows),
        'applicants': rows, 'comparison_rows': page, 'pool_size': len(rows),
        'score_deck_members': [{key: row[key] for key in ('application', 'rank', 'member_name',
            'member_number', 'score', 'higher', 'tied_others', 'lower')} for row in rows],
        'criteria': rows[0]['display_traces'] if rows else [],
        'active': active, 'problems': messages_for_officers(problems),
        'ranking_notice': workspace_notice(ready=active, result={'active': active}, inventory=[],
            configuration_pending=False, missing=[], problems=problems)})


def result_context(request, program, run, current, legacy_post=False):
    pk, run_id = program.pk, run.pk
    try:
        run.clean()
    except ValidationError:
        # Preserve history without exposing unvalidated scores or decisions.
        return {'run': run, 'invalid_calculation': True, 'active': False}
    active, problems = False, []
    try:
        with service.fence(pk, current) as (current, program, applications):
            service.current_result_run(program, applications, current, run.pk)
        active = True
    except ValidationError as error:
        problems = error.messages
    choices = {str(row.application_id): row for row in service.latest_decisions(program)}
    selecting = request.method == 'POST' and request.POST.get('action') == 'SELECT_ASSISTANCE'
    unselecting = request.method == 'POST' and request.POST.get('action') == 'UNSELECT_ASSISTANCE'
    deciding = request.method == 'POST' and (legacy_post or request.POST.get('action') == 'DECISION' or selecting or unselecting)
    form_class = UnselectAssistanceForm if unselecting else SelectAssistanceForm if selecting else DecisionForm
    submitted = form_class(request.POST if deciding else None, prefix='decision')
    if deciding and submitted.is_valid():
        try:
            if submitted.cleaned_data['run_id'] != run.pk:
                raise ValidationError('Submitted calculation does not match this page.')
            data = dict(submitted.cleaned_data)
            if selecting:
                data.update(outcome='SELECTED', reason=SelectAssistanceForm.audit_reason)
            if unselecting:
                service.unselect_assistance(pk, user=current, **data)
            else:
                service.record_decision(pk, user=current, **data)
            from django.urls import reverse
            return redirect(reverse('ewaf:operational_workspace', kwargs={'pk': pk})
                            + f'?run={run.pk}&review={data["application_id"]}#readiness')
        except ValidationError as error:
            submitted.add_error(None, error)
    simplify_form_errors(submitted)
    rows = service.ordered(run)
    from .score_breakdown import display, numeric
    from .household_criteria import NAMES
    contribution_columns = [{'code': trace['criterion'], 'name': NAMES.get(trace['criterion'], trace['criterion'])}
                            for trace in rows[0]['traces']] if rows else []
    references = {row['application']: row['reference'] for row in run.snapshot['manifest']}
    applications_by_id = {str(item.pk): item for item in program.applications.select_related('member')}
    members = {key: item.member.full_name for key, item in applications_by_id.items()}
    member_numbers = {str(key): number for key, number in program.applications.values_list('pk', 'member__control_number')}
    from assistance.models import AssistanceRelease
    received = {str(key) for key in AssistanceRelease.objects.successful().filter(
        application__program=program).values_list('application_id', flat=True)}
    for row in rows:
        row['reference'] = references[row['application']]
        row['member_name'] = members.get(row['application'], '')
        row['member_number'] = member_numbers.get(row['application'], '')
        application = applications_by_id.get(row['application'])
        row['application_status'] = application.status if application else ''
        row['rank'] = row['comparison']['higher'] + 1
        row['traces'] = [{**trace, 'verified_value': run.snapshot['eligible'][row['application']]['inputs'][trace['criterion']]['value']}
                         for trace in row['traces']]
        previous = choices.get(row['application'])
        row['decision'] = previous
        row['has_previous_decision'] = bool(previous and previous.run_id != run.pk)
        row['received'] = row['application'] in received
        from .workspace_ui import accepted_information, decision_state
        row['accepted_information'] = accepted_information(run, row['application'])
        row['decision_key'], row['decision_label'], row['decision_icon'] = decision_state(row, run)
        row['display_score'] = row.get('score_display') or row['score_0_100']
        row['contribution_points'] = [{'code': trace['criterion'], 'points': display(numeric(trace['contribution']) * 100)}
                                      for trace in row['traces']]
        row['is_selected'] = bool(previous and previous.run_id == run.pk and previous.outcome == 'SELECTED')
        row['is_unselected'] = bool(previous and previous.run_id == run.pk and previous.outcome == 'DEFERRED'
                                   and previous.review.get('selection_action') == 'unselected')
        row['can_unselect'] = row['is_selected'] and not row['received'] and current.has_perms(
            ('ewaf.decide_operational', 'assistance.decide_assistance'))
        row['tie_review'] = (row['comparison']['capacity_boundary_tie'] if run.configuration.uses_dataset_scoring
                             else row['comparison']['equal'] > 1)
        row['tie_held'] = row['tie_review'] and run.configuration.policy['tie_rule'] in ('hold', 'hold_boundary')
        row['select_form'] = SelectAssistanceForm(prefix='decision', auto_id='id_select_' + row['application'] + '_%s', initial={
            'run_id': run.pk, 'application_id': row['application'], 'expected_revision': previous.revision if previous else 0})
        row['unselect_form'] = UnselectAssistanceForm(prefix='decision', auto_id='id_unselect_' + row['application'] + '_%s', initial={
            'run_id': run.pk, 'application_id': row['application'], 'expected_revision': previous.revision if previous else 0})
        row['form'] = DecisionForm(prefix='decision', auto_id='id_' + row['application'] + '_%s', initial={
            'run_id': run.pk, 'application_id': row['application'], 'expected_revision': previous.revision if previous else 0})
    from .workspace_ui import DECISIONS
    query = request.GET.get('q', '').strip()[:200]
    decision_filter = request.GET.get('decision', '')
    if decision_filter not in dict(DECISIONS):
        decision_filter = ''
    pool_size = len(rows)
    selected_review = request.POST.get('decision-application_id', '') if deciding else request.GET.get('review', '')
    if selected_review and selected_review not in members:
        if not deciding:
            raise Http404
        selected_review = ''
    for row in rows:
        row['drawer_open'] = row['application'] == selected_review
        if deciding and row['drawer_open']:
            row['unselect_form' if unselecting else 'select_form' if selecting else 'form'] = submitted
    selected_row = next((row for row in rows if row['application'] == selected_review), None)
    if query:
        rows = [row for row in rows if query.casefold() in ' '.join(
            (row['member_name'], row['reference'], row['member_number'])).casefold()]
    if decision_filter:
        rows = [row for row in rows if row['decision_key'] == decision_filter]
    selected_index = next((index for index, row in enumerate(rows) if row['drawer_open']), 0)
    page = Paginator(rows, 50).get_page(request.GET.get('page', selected_index // 50 + 1))
    if not selected_review and page:
        selected_row = page[0]
    for row in page:
        row['panel_selected'] = selected_row is not None and row['application'] == selected_row['application']
    history = Paginator(Decision.objects.filter(program=program), 50).get_page(request.GET.get('decisions_page'))
    for item in history:
        item.clean()
    from .revised.rolling_pool import selection_waiting as waiting_for_final
    selection_waiting = waiting_for_final(run.snapshot, run.configuration)
    return {'run': run, 'rows': page, 'pool_size': pool_size, 'query': query,
        'contribution_columns': contribution_columns, 'table_columns': len(contribution_columns) + 4,
        'selected_row': selected_row,
        'decision_filter': decision_filter, 'decision_options': DECISIONS,
        'active': active, 'problems': messages_for_officers(problems), 'submitted': submitted, 'history': history,
        'selection_waiting': selection_waiting,
        'can_decide': not selection_waiting and current.has_perms(('ewaf.decide_operational', 'assistance.decide_assistance'))}
