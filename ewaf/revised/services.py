"""Private synthetic workflow. No branch authorizes real scoring or selection."""
from contextlib import contextmanager
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from programs.models import Program
from programs.terms import terms_lock, snapshot_terms, terms_digest
from core.permissions import require_workspace_permissions
from ewaf.operational_services import actor as operational_actor
from ewaf.evidence import canonical as evidence_canonical, digest
from ewaf.evidence_services import reasoned
from ewaf.evidence_records import recording
from .models import RevisedPreviewRun as Run, RevisedPreviewReview as Review
from .engine import METHOD, SOURCE_SHA256, configure, calculate, CalculationError
from .fixtures import example_pool

BLOCKERS = (
    ('SI_RUBRIC', 'SI needs an authorized numerical assessment rubric. Supporting documents and 4Ps status are evidence, not a numerical mapping.'),
    ('WEIGHT_AUTHORITY', 'Record actual authorized pairwise judgments and strict CI/CR validation, or a separately approved manual weighting method. The reconstructed example and sliders grant no authority.'),
    ('ACCEPTED_EVIDENCE_HANDOFF', 'Use the separately gated dataset-policy workflow with an approved program binding and current accepted evidence. This synthetic preview cannot supply accepted HI/SI/ES/HM inputs from registration approval, raw member fields or review notes.'),
    ('MEASUREMENT_POLICY', 'Approve income/household definitions, assessment periods, employment categories and the qualifying actual-release scope and period for PA.'),
    ('NORMALIZATION_POLICY', 'Approve dataset-based normalization and directions for the complete frozen eligible pool; resolve missing, disputed, stale and constant-column inputs.'),
    ('RANKING_POLICY', 'Record competition ranking and the human procedure for ties at a capacity boundary. Ranking never selects a beneficiary.'),
    ('CONFIGURATION_AUTHORITY', 'A separately authorized, versioned, locked configuration with current evidence and program scope is required. Existing four-criterion and Vault approvals do not authorize this method.'),
    ('OPERATIONAL_ENABLEMENT', 'This page is a synthetic preview only. Official runs require separate dataset-policy and scoring enablement; the preview cannot activate either or publish results.'),
)


def official_readiness(program=None):
    # Official scoring belongs to the separately gated dataset-policy workflow.
    # No policy, settings override or configuration can turn this preview into an official run.
    from .policy import BINDING_BLOCKER
    return [{'code': code, 'message': message} for code, message in (*BLOCKERS, BINDING_BLOCKER)]


def persist(artifact):
    artifact.digest = digest(artifact.payload())
    artifact.audit_entry = LogEntry.objects.create(user=artifact.actor,
        content_type=ContentType.objects.get_for_model(type(artifact)), object_id=artifact.digest,
        object_repr='Private synthetic revised EWAF ' + artifact._meta.model_name,
        action_flag=ADDITION, change_message=artifact.digest)
    with recording():
        artifact.save()
    return artifact


def require_official_ready(program=None):
    raise ValidationError([f'{row["code"]}: {row["message"]}' for row in official_readiness(program)])


def actor(user, action='view'):
    current = operational_actor(user)
    require_workspace_permissions(current, 'ewaf.view_revisedpreview',
                                  *([f'ewaf.{action}_revisedpreview'] if action != 'view' else []))
    return current


def available():
    tables = set(connection.introspection.table_names())
    return all(model._meta.db_table in tables for model in (Run, Review))


def source_context(program):
    # Synthetic inputs have no connection to real member/evidence rows. Retain the
    # program context, but never read raw profiles to fill absent accepted inputs.
    return evidence_canonical({'method': METHOD, 'document': SOURCE_SHA256,
        'program_version': program.version, 'terms': terms_digest(snapshot_terms(program)),
        'policy_authorized_at': program.policy_authorized_at,
        'policy_authorized_by': program.policy_authorized_by_id,
        'input_source': 'document-synthetic-fixture-v1'})


def token(program):
    latest = Run.objects.filter(program=program).first()
    return digest({'source': source_context(program), 'latest': latest.digest if latest else None})


@contextmanager
def fence(program_id, user, action):
    with terms_lock():
        current = actor(user, action)
        authority = (current.pk, current.is_superuser, frozenset(current.get_all_permissions()))
        program = Program.objects.select_for_update().get(pk=program_id)
        if not program.ewaf_applicable:
            raise ValidationError('Choose an EWAF program context for this synthetic preview.')
        yield current, program
        final = actor(user, action)
        if authority != (final.pk, final.is_superuser, frozenset(final.get_all_permissions())):
            raise PermissionDenied('Preview authority changed. Reload before continuing.')


def preview(*, user, mode='DOCUMENT_EXAMPLE', proposed=None, classify=True, capacity=None, program=None):
    actor(user, 'calculate')
    try:
        config = configure(mode, proposed, classify=classify)
        pool = example_pool(str(program.pk) if program else 'SYNTHETIC-DOCUMENT-EXAMPLE')
        return config, pool, calculate(pool, config, capacity=capacity)
    except CalculationError as error:
        raise ValidationError(str(error)) from error


def retain(program_id, *, user, expected, request_key, mode='DOCUMENT_EXAMPLE', proposed=None,
           classify=True, capacity=None, reason):
    with fence(program_id, user, 'calculate') as (current, program):
        fields = reasoned(current, reason, True)
        try:
            request_key = UUID(str(request_key))
        except (ValueError, TypeError) as error:
            raise ValidationError('A valid preview request identity is required.') from error
        config, pool, result = preview(user=current, mode=mode, proposed=proposed, classify=classify, capacity=capacity, program=program)
        request_digest = digest({'actor': current.pk, 'expected': expected, 'configuration': config.digest,
                                'pool': pool.digest, 'capacity': capacity, 'reason': fields['reason']})
        previous_request = Run.objects.filter(program=program, request_key=request_key).first()
        if previous_request:
            previous_request.clean()
            if previous_request.request_digest != request_digest or previous_request.source_context != source_context(program):
                raise ValidationError('Preview request or program context changed. Reload before retaining a new version.')
            return previous_request
        if expected != token(program):
            raise ValidationError('Preview history or program context changed. Reload before retaining a new version.')
        previous = Run.objects.filter(program=program).first()
        return persist(Run(program=program, revision=previous.revision + 1 if previous else 1,
            previous=previous, method=METHOD, mode=mode, configuration=config.data, pool=pool.data,
            result=result, source_context=source_context(program), capacity_example=capacity,
            request_key=request_key, request_digest=request_digest, **fields))


def current(run):
    return (run.source_context == source_context(Program.objects.get(pk=run.program_id))
            and Run.objects.filter(program_id=run.program_id).first().pk == run.pk)


def review_token(run):
    last = Review.objects.filter(run=run).first()
    return digest({'run': run.digest, 'context': token(run.program), 'review': last.digest if last else None})


def review(run_id, *, user, expected, finding, reason):
    program_id = Run.objects.values_list('program_id', flat=True).get(pk=run_id)
    with fence(program_id, user, 'review') as (current_actor, program):
        run = Run.objects.get(pk=run_id, program=program)
        run.clean()
        if not current(run) or expected != review_token(run):
            raise ValidationError('This preview or review is stale. Review the current retained version.')
        if finding not in ('REVIEWED', 'CORRECTIONS_REQUESTED'):
            raise ValidationError('Reviewing a demonstration cannot approve scoring or select beneficiaries.')
        previous = Review.objects.filter(run=run).first()
        return persist(Review(program=program, run=run, run_digest=run.digest,
            revision=previous.revision + 1 if previous else 1, previous=previous, finding=finding,
            **reasoned(current_actor, reason, True)))


def export(run_id, *, user, format='json'):
    program_id = Run.objects.values_list('program_id', flat=True).get(pk=run_id)
    with fence(program_id, user, 'export') as (current_actor, program):
        run = Run.objects.get(pk=run_id, program=program)
        run.clean()
        is_current = current(run)
        if format == 'json':
            from .engine import canonical
            payload = {'record': run.payload(), 'digest': run.digest,
                'current_synthetic_context': is_current, 'official': False,
                'notice': 'Private synthetic demonstration. No beneficiary decisions.'}
            data = canonical(payload).encode()
        elif format in ('csv', 'xlsx'):
            from reports.services import csv_bytes, xlsx_bytes
            columns = ['Method', 'Mode', 'Revision', 'Current synthetic context', 'Applicant',
                'Internal rank', 'Tie group', 'Boundary tie', 'Score exact', 'Score display', 'Classification',
                'Criterion', 'Raw input', 'Encoded exact', 'Dataset lower', 'Dataset upper', 'Direction',
                'Normalized exact', 'Weight exact', 'Contribution points exact', 'Evidence version', 'Human decision']
            rows = [[METHOD, run.mode, run.revision, is_current, row['applicant'], row['rank'], row['tie_group'],
                row['capacity_boundary_tie'], row['score_0_100']['exact'], row['display_score'], row['classification'],
                trace['criterion'], trace['input']['value'], trace['encoded']['exact'], trace['lower']['exact'],
                trace['upper']['exact'], trace['direction'], trace['normalized']['exact'], trace['weight']['exact'],
                trace['contribution_points']['exact'], trace['input']['evidence_version'], row['human_decision']]
                for row in run.result['applicants'] for trace in row['traces']]
            data = (csv_bytes if format == 'csv' else xlsx_bytes)(columns, rows)
        else:
            raise ValidationError('Choose JSON, CSV or Excel for a private preview export.')
        LogEntry.objects.create(user=current_actor, content_type=ContentType.objects.get_for_model(Run),
            object_id=run.digest, object_repr='Private synthetic revised EWAF export', action_flag=CHANGE,
            change_message=f'revised_preview_export; format={format}; run_digest={run.digest}')
        return data
