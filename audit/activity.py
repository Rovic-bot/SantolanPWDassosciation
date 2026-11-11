"""Read-only administration activity, projected from the original audit histories.

Labels and filters share the same SQL expressions. Historical outcomes come from
the recorded snapshot, never the current application/member state. No audit is
rewritten or copied into another log.
"""
from dataclasses import dataclass

from django.apps import apps
from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.functions import Cast, Coalesce, Concat, NullIf


AREAS = {
    'members': 'Members & membership', 'programs': 'Programs & applications',
    'assistance': 'Eligibility & assistance', 'ewaf': 'EWAF & selection',
    'announcements': 'Announcements & results', 'events': 'Events & attendance',
    'pdao': 'PDAO applications', 'help': 'Assistance Desk',
    'content': 'Website content', 'reports': 'Reports & exports', 'administration': 'Accounts & settings',
}

# Presentation groups only: the original action and its historical outcome stay
# unchanged. The same expression drives badges, summary counts and filters.
KINDS = {
    'approval': ('Approved', 'Approvals', 'check'),
    'access': ('Document access', 'Documents & prints', 'download'),
    'publication': ('Published', 'Publications', 'publish'),
    'selection': ('Selection', 'Selection decisions', 'members'),
    'change': ('Changed', 'Changes', 'edit'),
    'other': ('Recorded', 'Other actions', 'activity'),
}


def kind_expression():
    return label_case([
        (Q(activity_label__in=('Member approved', 'Program policy approved',
            'External program approval recorded', 'Assistance approved / member selected',
            'Member marked eligible and automatically selected')), 'approval'),
        (Q(activity_label__in=('Document downloaded', 'Application photo viewed', 'Membership form viewed',
            'PDAO form opened for printing', 'Assistance document viewed', 'EWAF preview exported',
            'Report viewed or exported')), 'access'),
        (Q(activity_label__endswith=' published'), 'publication'),
        (Q(activity_label__in=('Member selected', 'Member not selected', 'Member unselected',
            'Selection deferred', 'Selection returned for review', 'Selection decision recorded')), 'selection'),
        (Q(activity_label__endswith=' changed') | Q(activity_label__endswith=' corrected') |
         Q(activity_label__endswith=' updated') | Q(activity_label__endswith=' saved'), 'change'),
    ], 'other')


def label_case(rules, default):
    return Case(*(When(condition, then=Value(label)) for condition, label in rules),
                default=Value(default), output_field=CharField())


def actions(mapping, field='action'):
    return [(Q(**{field: code}), label) for code, label in mapping.items()]


def person_and_program(prefix='application'):
    return Concat(F(prefix + '__member__full_name'), Value(' · '),
                  F(prefix + '__program__name'), output_field=CharField())


@dataclass(frozen=True)
class Source:
    key: str
    model: str
    area: str
    permissions: tuple
    record: object
    rules: tuple = ()
    default: str = 'Activity recorded'
    time: str = 'occurred_at'
    actor: str = 'actor'
    actor_label: str = 'actor_label'
    note: str = 'notes'
    include: object = None
    exclude: object = None
    area_rules: tuple = ()

    def queryset(self):
        query = apps.get_model(self.model).objects.order_by()
        if self.include is not None:
            query = query.filter(self.include)
        if self.exclude is not None:
            query = query.exclude(self.exclude)
        # Public submissions without a staff actor are not administrator actions.
        staff = Q(**{self.actor + '__isnull': False})
        if self.actor_label:
            staff |= ~Q(**{self.actor_label: ''})
        query = query.filter(staff)
        username = F(self.actor + '__username')
        actor = Coalesce(NullIf(F(self.actor_label), Value('')), username,
                         Value('Former administrator')) if self.actor_label else username
        return query.annotate(
            activity_id=Cast('pk', CharField()), activity_source=Value(self.key),
            activity_time=F(self.time), activity_actor=actor,
            activity_area=label_case(self.area_rules, self.area), activity_record=self.record,
            activity_label=label_case(self.rules, self.default),
        ).annotate(activity_kind=kind_expression())


def sources():
    # Operational decisions already have a mandatory ProgramLog companion. Show
    # their descriptive immutable decision once, not the companion digest too.
    decisions = apps.get_model('ewaf.OperationalDecision')
    technical = Q(action__startswith='g12_') | Q(action__startswith='durable_')
    program_rules = actions({
        'created': 'Program created', 'updated': 'Program changed',
        'published': 'Program published', 'draft': 'Program unpublished',
        'archived': 'Program archived', 'cancelled': 'Program cancelled',
        'policy_authorized': 'Program policy approved', 'picture_updated': 'Program picture changed',
        'disability_types_configured': 'Program requirements changed',
        'requirement_added': 'Program requirement added', 'requirement_updated': 'Program requirement changed',
        'pdao_recorded': 'External program approval recorded', 'terms_recorded': 'Program terms saved',
        'approval_bound': 'Program approval linked', 'application_updated': 'Application changed',
        'application_corrected': 'Application corrected', 'document_downloaded': 'Document downloaded',
        'photo_viewed': 'Application photo viewed', 'submitted': 'Application recorded',
        'current_information_reviewed': 'Member information confirmed',
        'decision_email_retry': 'Decision email retried',
        'ewaf_required': 'Program EWAF setting changed',
    })
    program_rules = [
        (Q(action='photo_verified', changes__photo_review__after__outcome='VERIFIED'), 'Application photo verified'),
        (Q(action='photo_verified', changes__photo_review__after__outcome='REJECTED'), 'Application photo rejected'),
        (Q(action='photo_verified', changes__photo_review__after__outcome='NEEDS_RESUBMISSION'), 'Photo resubmission requested'),
        (Q(action='photo_verified'), 'Application photo reviewed'),
    ] + program_rules
    program_record = Case(When(application__isnull=False, then=person_and_program()),
                          default=F('program__name'), output_field=CharField())
    membership_actions = {
        'approved': 'Member approved', 'rejected': 'Membership rejected',
        'onsite_encoded': 'Membership application recorded',
        'prpwd_verified': 'Membership verification confirmed',
        'prpwd_not_verified': 'Membership verification not confirmed',
        'document_downloaded': 'Document downloaded',
    }
    # Registration approval actions mirror the MembershipEvent in the same
    # transaction. Keep the canonical membership decision and all other steps.
    registration_mirrors = ('registration_approved', 'registration_rejected',
                            'membership_approved', 'membership_rejected', 'membership_verification')
    assistance_rules = [
        (Q(action='eligibility_reviewed', snapshot__automatic_selection='non_ewaf_all_eligible_v1'), 'Member marked eligible and automatically selected'),
        (Q(action='eligibility_reviewed', snapshot__after__eligibility='eligible'), 'Member marked eligible'),
        (Q(action='eligibility_reviewed', snapshot__after__eligibility='ineligible'), 'Member marked ineligible'),
        (Q(action='eligibility_reviewed', snapshot__after__eligibility='review'), 'More information requested'),
        (Q(action='decision_recorded', snapshot__after__decision='approved'), 'Assistance approved / member selected'),
        (Q(action='decision_recorded', snapshot__after__decision='rejected'), 'Member not selected'),
        (Q(action='decision_recorded', snapshot__after__decision='pending'), 'Selection returned for review'),
    ] + actions({'eligibility_reviewed': 'Eligibility reviewed', 'decision_recorded': 'Selection decision recorded',
        'assistance_released': 'Assistance released', 'release_voided': 'Assistance release voided',
        'application_cancelled': 'Application cancelled', 'evidence_invalidated': 'Application review required'})
    return [
        Source('program', 'programs.ProgramLog', 'programs', ('programs.view_program', 'programs.view_programapplication'),
               program_record, program_rules, 'Program activity recorded', exclude=technical),
        Source('ewaf', 'programs.ProgramLog', 'ewaf', ('ewaf.view_operational',), program_record,
               actions({'g12_operationalconfiguration': 'EWAF configuration saved',
                        'g12_operationalrun': 'EWAF scores calculated',
                        'g12_datasetinputreview': 'EWAF inputs reviewed',
                        'g12_criterionassessment': 'EWAF evidence assessed',
                        'g12_evidencepolicyrevision': 'EWAF evidence policy saved',
                        'g12_operationaldecision': 'Selection decision recorded'}),
               'EWAF activity recorded', include=technical,
               exclude=Q(pk__in=decisions.objects.values('audit_entry_id'))),
        Source('selection', 'ewaf.OperationalDecision', 'ewaf', ('ewaf.view_operational', 'assistance.view_assistancecase'),
               person_and_program(), [(Q(review__selection_action='unselected'), 'Member unselected')]
               + actions({'SELECTED': 'Member selected', 'NOT_SELECTED': 'Member not selected',
                          'DEFERRED': 'Selection deferred'}, 'outcome'),
               'Selection decision recorded', time='recorded_at', note='reason'),
        Source('assistance', 'assistance.AssistanceLog', 'assistance',
               ('assistance.view_assistancecase', 'programs.view_programapplication'), person_and_program(),
               assistance_rules, 'Assistance activity recorded'),
        Source('membership', 'membership.MembershipEvent', 'members', ('membership.view_membershipapplication',),
               F('application__full_name'), actions(membership_actions), 'Membership activity recorded', note='description'),
        Source('registration', 'membership.RegistrationAction', 'members', ('membership.view_registrationintake',),
               Coalesce(F('intake__membership_application__full_name'), F('intake__reference')),
               actions({'received': 'Membership application recorded', 'begin_review': 'Membership review started',
                        'request_information': 'More information requested', 'ready_for_onsite': 'Onsite review requested',
                        'presented_printout': 'Membership printout received', 'correction_recorded': 'Membership details corrected',
                        'onsite_observations': 'Onsite findings recorded', 'membership_handoff': 'Membership review prepared',
                        'office_information_verified': 'Member information verified onsite',
                        'approval_email_retry': 'Membership approval email retried',
                        'pending_email_requested': 'Membership reminder requested', 'pending_email_retry': 'Membership reminder retried',
                        'office_verification_email_requested': 'Office verification email requested',
                        'staff_form_viewed': 'Membership form viewed', 'staff_completed_form_viewed': 'Membership form viewed',
                        'private_document_downloaded': 'Document downloaded'}),
               'Membership activity recorded', note='reason', exclude=Q(action__in=registration_mirrors)),
        Source('member', 'members.MemberEvent', 'members', ('members.view_member',), F('member__full_name'),
               actions({'profile_updated': 'Member details changed', 'status_changed': 'Member status changed',
                        'member_update_submitted': 'Member information update requested',
                        'member_update_invited': 'Member invited for office verification',
                        'member_update_email_retry': 'Member verification email retried',
                        'member_update_approved': 'Member information update approved',
                        'member_update_needs_verification': 'Member marked needs verification',
                        'document_downloaded': 'Document downloaded', 'document_verified': 'Member document verified',
                        'document_verification_failed': 'Member document rejected', 'prpwd_verified': 'Membership verification confirmed'}),
               'Member activity recorded', exclude=Q(action='email_added_from_application', actor__isnull=True)),
        Source('information', 'members.InformationReviewAction', 'members', ('members.view_informationreview',),
               F('review__member__full_name'), actions({'received': 'Member information review started',
                   'review_note': 'Member information review updated', 'opened': 'Member information review started',
                   'confirmed': 'Member information confirmed', 'needs_information': 'More information requested',
                   'rejected': 'Member information rejected', 'closed': 'Member information review closed'}),
               'Member information reviewed', note='reason'),
        Source('pdao', 'membership.PDAORegistrationEvent', 'pdao', ('membership.view_pdaoregistration',),
               Concat(Value('PDAO application '), Cast('registration_id', CharField())),
               actions({'onsite_submitted': 'PDAO application recorded', 'details_viewed': 'PDAO application viewed',
                        'print_viewed': 'PDAO form opened for printing', 'ready': 'PDAO application marked ready',
                        'forwarded': 'PDAO forwarding recorded', 'corrected': 'PDAO application corrected',
                        'needs_info': 'PDAO information requested', 'email_retry': 'PDAO email retried',
                        'claim_notice_queued': 'PWD ID claim notice requested'}), 'PDAO activity recorded', note=''),
        Source('announcement', 'announcements.AnnouncementEvent', 'announcements', ('announcements.view_announcement',),
               F('announcement__title'), actions({'created': 'Announcement created', 'updated': 'Announcement changed',
                   'published': 'Announcement published', 'draft': 'Announcement unpublished',
                   'archived': 'Announcement archived', 'deleted': 'Announcement deleted',
                   'results_prepared': 'Results prepared', 'results_published': 'Results published',
                   'certificates_retried': 'Certificate delivery retried'}), 'Announcement activity recorded', note='description'),
        Source('event', 'events.EventLog', 'events', ('events.view_event',), F('event__title'),
               actions({'created': 'Event created', 'updated': 'Event changed', 'published': 'Event published',
                        'draft': 'Event unpublished', 'archived': 'Event archived', 'cancelled': 'Event cancelled',
                        'registration_updated': 'Event registration changed'}), 'Event activity recorded'),
        Source('attendance', 'events.EventAttendanceLog', 'events', ('events.view_eventattendance',),
               F('attendance__event__title'), actions({'recorded': 'Attendance recorded', 'corrected': 'Attendance corrected'}),
               'Attendance activity recorded'),
        Source('observance', 'events.AnnualObservanceLog', 'events', ('events.view_annualobservance',),
               F('observance__title'), actions({'created': 'Annual observance created', 'updated': 'Annual observance changed',
                   'published': 'Annual observance published', 'draft': 'Annual observance unpublished',
                   'archived': 'Annual observance archived'}), 'Annual observance changed', note='reason'),
        Source('content', 'core.ContentRevision', 'content', ('core.view_publiccontent',), F('content__title'),
               actions({'draft': 'Website content changed', 'publish': 'Website content published',
                        'withdraw': 'Website content unpublished', 'archive': 'Website content archived'}),
               'Website content changed', note='reason'),
        Source('portal', 'core.PortalPageRevision', 'content', ('core.view_publiccontent',), F('page_id'),
               actions({'draft': 'Website page changed', 'publish': 'Website page published'}), 'Website page changed', note=''),
        Source('help', 'assistance.ReferralAction', 'help', ('assistance.view_referralticket',), F('ticket__reference'),
               actions({'review_started': 'Assistance request opened', 'reviewed': 'Assistance request reviewed',
                   'quick_gmail_reply_recorded': 'Assistance reply recorded', 'quick_status_updated': 'Assistance request status changed',
                   'evidence_viewed': 'Assistance document viewed', 'replied': 'Assistance reply recorded',
                   'closed': 'Assistance request closed', 'reopened': 'Assistance request reopened'}), 'Assistance request updated', time='recorded_at'),
        Source('email_settings', 'assistance.ReferralSettingsEvent', 'help', ('assistance.view_referralsettings',),
               Value('Association email settings'), default='Email settings changed', time='recorded_at', actor_label='', note='reason'),
        legacy_source(),
    ]


def legacy_source():
    rules = []
    for app, model, name in [('auth', 'user', 'Administrator account'), ('auth', 'group', 'Role'),
            ('members', 'disabilitytype', 'Disability classification'),
            ('documents', 'documenttype', 'Document type'), ('documents', 'membershipdocumentrequirement', 'Document requirement'),
            ('membership', 'membershipsettings', 'Registration settings'),
            ('assistance', 'eligibilitystatus', 'Eligibility settings')]:
        for flag, verb in [(1, 'added'), (2, 'changed'), (3, 'deleted')]:
            rules.append((Q(content_type__app_label=app, content_type__model=model, action_flag=flag), f'{name} {verb}'))
    rules += [(Q(content_type__app_label='ewaf', content_type__model='vaultrevision'), 'EWAF weights saved'),
              (Q(content_type__app_label='ewaf', content_type__model='shareddatasetpolicy'), 'EWAF scoring policy saved'),
              (Q(content_type__app_label='ewaf', change_message__startswith='revised_preview_export;'), 'EWAF preview exported'),
              (Q(content_type__app_label='ewaf'), 'EWAF record saved'),
              (Q(change_message__startswith='Report '), 'Report viewed or exported')]
    rules += actions({1: 'Record added', 2: 'Record changed', 3: 'Record deleted'}, 'action_flag')
    area_rules = [(Q(content_type__app_label=app), area) for app, area in (
        ('ewaf', 'ewaf'), ('members', 'members'), ('membership', 'members'),
        ('programs', 'programs'), ('events', 'events'), ('announcements', 'announcements'),
        ('assistance', 'assistance'), ('core', 'content'))]
    area_rules.append((Q(change_message__startswith='Report '), 'reports'))
    return Source('administration', 'admin.LogEntry', 'administration', (), F('object_repr'), rules,
                  'Administration activity recorded', time='action_time', actor='user', actor_label='',
                  note='change_message', area_rules=area_rules)


FIELDS = ('activity_id', 'activity_source', 'activity_time', 'activity_actor',
          'activity_area', 'activity_record', 'activity_label', 'activity_kind')


def permitted_sources(user):
    return [source for source in sources() if user.has_perms(source.permissions)]


def combine(queries, fields=FIELDS, *, distinct=False):
    projections = [query.values(*fields) for query in queries]
    return projections[0].union(*projections[1:], all=not distinct)


def filtered_queries(sources, values):
    for source in sources:
        query = source.queryset()
        if values.get('area'):
            query = query.filter(activity_area=values['area'])
        if values.get('activity'):
            query = query.filter(activity_label=values['activity'])
        if values.get('kind'):
            query = query.filter(activity_kind=values['kind'])
        if values.get('actor'):
            query = query.filter(activity_actor=values['actor'])
        if values.get('q'):
            for word in values['q'].split():
                match = (Q(activity_label__icontains=word) | Q(activity_record__icontains=word)
                         | Q(activity_actor__icontains=word))
                if source.note:
                    match |= Q(**{source.note + '__icontains': word})
                query = query.filter(match)
        from datetime import datetime, time
        from django.utils import timezone
        for key, lookup, boundary in [('date_from', 'gte', time.min), ('date_to', 'lte', time.max)]:
            if values.get(key):
                query = query.filter(**{source.time + '__' + lookup:
                    timezone.make_aware(datetime.combine(values[key], boundary))})
        yield query
