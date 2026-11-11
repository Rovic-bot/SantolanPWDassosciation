import uuid
import secrets
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from core.reference_services import ShortReferenceMixin
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.dateformat import format as format_date


def application_reference():
    """Historical migrations only. New submissions use workflow.allocate_reference."""
    return 'SPA-' + secrets.token_hex(8).upper()


def status_token():
    return secrets.token_urlsafe(32)


class ProgramQuerySet(models.QuerySet):
    def public(self, *, at=None):
        at = timezone.now() if at is None else at
        return self.filter(status__in=['published', 'cancelled'], published_at__lte=at)

    @staticmethod
    def _application_availability_condition(at):
        # Match Python str.strip() whitespace, including Unicode and the four
        # ASCII separators that MySQL's generic whitespace class can omit.
        non_whitespace = '[^\t-\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]'
        condition = models.Q(
            status='published', published_at__lte=at,
            registration_opens_at__lte=at, registration_closes_at__gt=at,
            policy_authorized_at__isnull=False,
            photo_instructions__regex=non_whitespace,
            selection_method__regex=non_whitespace,
        )
        condition &= (models.Q(organizational_event__isnull=True) |
                      models.Q(organizational_event__status='published', organizational_event__published_at__lte=at))
        if settings.PDAO_ENFORCEMENT_ENABLED:
            from .approval_policy import binding_condition
            condition &= binding_condition(at=at)
        return condition

    def accepting_applications(self, *, at=None):
        """Query equivalent of registration_available; preserve its policy and boundaries."""
        at = timezone.now() if at is None else at
        return self.filter(self._application_availability_condition(at))

    def with_public_application_status(self, *, at):
        """Label public rows at one instant; application services still enforce policy."""
        return self.annotate(public_application_status=models.Case(
            models.When(status='cancelled', then=models.Value('cancelled')),
            models.When(registration_closes_at__lte=at, then=models.Value('ended')),
            models.When(registration_opens_at__gt=at, then=models.Value('upcoming')),
            models.When(self._application_availability_condition(at), then=models.Value('open')),
            default=models.Value('unavailable'), output_field=models.CharField(),
        ))


class Program(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'
        ARCHIVED = 'archived', 'Archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    public_code = models.CharField(max_length=9, unique=True, null=True, blank=True, editable=False)
    ewaf_applicable = models.BooleanField(default=True, editable=False)
    selection_method = models.TextField(max_length=2000, blank=True)
    photo_instructions = models.TextField(max_length=2000, blank=True)
    resubmission_closes_at = models.DateTimeField(null=True, blank=True)
    policy_authorized_at = models.DateTimeField(null=True, blank=True, editable=False)
    policy_authorized_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', editable=False)
    description = models.TextField(max_length=20000, blank=True)
    assistance_type = models.CharField(max_length=120, blank=True)
    eligible_disability_types = models.ManyToManyField('members.DisabilityType', related_name='programs')
    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_closes_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    slots = models.PositiveIntegerField(null=True, validators=[MinValueValidator(1)])
    budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    benefit = models.CharField(max_length=1000, blank=True)
    requirements = models.TextField(max_length=10000, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_programs')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_programs')
    version = models.PositiveIntegerField(default=0)
    objects = ProgramQuerySet.as_manager()

    @property
    def initials(self):
        return ''.join(word[0] for word in re.findall(r'[^\W_]+', self.name)[:2]).upper() or 'P'

    class Meta:
        ordering = ['-created_at', '-pk']
        default_permissions = ('add', 'change', 'view')
        permissions = [('publish_program', 'Can publish, withdraw, cancel and archive programs'),
                       ('configure_program', 'Can configure program requirements and questions')]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'published', 'cancelled', 'archived']), name='program_valid_status'),
            models.CheckConstraint(condition=~models.Q(status__in=['published', 'cancelled']) | models.Q(published_at__isnull=False), name='public_program_has_date'),
            models.CheckConstraint(condition=~models.Q(status__in=['published', 'cancelled']) | (models.Q(registration_opens_at__isnull=False, registration_closes_at__isnull=False) & ~models.Q(name='') & ~models.Q(assistance_type='')), name='public_program_complete'),
            models.CheckConstraint(condition=models.Q(registration_closes_at__gt=models.F('registration_opens_at')), name='program_registration_order'),
            models.CheckConstraint(condition=models.Q(ends_at__isnull=True) | models.Q(starts_at__isnull=True) | models.Q(ends_at__gt=models.F('starts_at')), name='program_period_order'),
            models.CheckConstraint(condition=models.Q(ends_at__isnull=True) | models.Q(registration_closes_at__lte=models.F('ends_at')), name='program_registration_before_end'),
            models.CheckConstraint(condition=models.Q(slots__isnull=True) | models.Q(slots__gte=1), name='program_positive_slots'),
            models.CheckConstraint(condition=models.Q(budget__isnull=True) | models.Q(budget__gte=0), name='program_nonnegative_budget'),
            models.CheckConstraint(condition=models.Q(amount__isnull=True) | models.Q(amount__gte=0), name='program_nonnegative_amount'),
        ]

    def clean(self):
        errors = {}
        if not self.ewaf_applicable:
            errors['__all__'] = 'Every program must use EWAF.'
        if self.status in ('published', 'cancelled'):
            errors.update(self.publication_errors())
        if self.registration_opens_at and self.registration_closes_at and self.registration_closes_at <= self.registration_opens_at:
            errors['registration_closes_at'] = 'Applications must close after they open.'
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors['ends_at'] = 'The program must end after it starts.'
        if self.ends_at and self.registration_closes_at and self.registration_closes_at > self.ends_at:
            errors['registration_closes_at'] = 'Close applications no later than the program end.'
        if errors:
            raise ValidationError(errors)

    def publication_errors(self):
        required = ('name', 'assistance_type', 'registration_opens_at', 'registration_closes_at', 'slots')
        return {name: 'Complete this field before publishing.' for name in
                required
                if not (getattr(self, name).strip() if isinstance(getattr(self, name), str) else getattr(self, name))}

    @property
    def slot_limit(self):
        return self.slots

    @property
    def capacity_label(self):
        return str(self.slots) if self.slots is not None else 'Not set'

    @property
    def allows_all_disability_types(self):
        from .mandatory_ewaf import retained_all_types
        return retained_all_types(self)

    @property
    def eligibility_profile_types(self):
        """Display the included catalog without rewriting unrestricted terms."""
        selected = self.eligible_disability_types.all()
        if selected:
            return selected
        if self.allows_all_disability_types:
            from members.disability_catalog import current_types
            return current_types().filter(is_active=True)
        return selected

    @property
    def registration_available(self):
        now = timezone.now()
        available = (self.status == 'published' and self.published_at is not None and self.published_at <= now
                and self.registration_opens_at is not None and self.registration_closes_at is not None
                and self.registration_opens_at <= now < self.registration_closes_at
                and self.policy_authorized_at is not None and bool(self.photo_instructions.strip())
                and bool(self.selection_method.strip()))
        if not available:
            return False
        event = getattr(self, 'organizational_event', None)
        if event and (event.status != 'published' or not event.published_at or event.published_at > now):
            return False
        if settings.PDAO_ENFORCEMENT_ENABLED:
            from .approval_policy import binding_condition
            return type(self).objects.filter(pk=self.pk).filter(binding_condition(at=now)).exists()
        return True

    def __str__(self):
        return self.name or 'Untitled program'


def program_picture_path(instance, filename):
    return f'program-pictures/{instance.program_id}/{uuid.uuid4().hex}.png'


class ProgramPicture(models.Model):
    """Presentation artwork, separate from approved program terms and evidence."""
    program = models.OneToOneField(Program, primary_key=True, on_delete=models.CASCADE, related_name='picture_asset')
    image = models.FileField(upload_to=program_picture_path, blank=True, max_length=250)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')


class ProgramRequirement(models.Model):
    class Kind(models.TextChoices):
        DOCUMENT = 'document', 'Document upload'
        TEXT = 'text', 'Written answer'
        ACKNOWLEDGEMENT = 'acknowledgement', 'Acknowledgement checkbox'

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='configured_requirements')
    reusable_document_type = models.ForeignKey('documents.DocumentType', null=True, blank=True, on_delete=models.PROTECT,
        help_text='For document requirements only: reuse a current explicitly verified internal document of this type.')
    label = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    instructions = models.CharField(max_length=1000, blank=True)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(kind__in=['document', 'text', 'acknowledgement']), name='program_requirement_valid_kind')]


class ProgramApplication(ShortReferenceMixin, models.Model):
    class Status(models.TextChoices):
        PENDING_PHOTO_VERIFICATION = 'PENDING_PHOTO_VERIFICATION', 'Pending Photo Verification'
        PHOTO_VERIFIED = 'PHOTO_VERIFIED', 'Photo Verified'
        VERIFICATION_FAILED = 'VERIFICATION_FAILED', 'Verification Failed'
        NEEDS_INFORMATION = 'NEEDS_INFORMATION', 'Needs Information'
        ELIGIBILITY_REVIEW = 'ELIGIBILITY_REVIEW', 'Eligibility Review'
        ELIGIBLE = 'ELIGIBLE', 'Eligible'
        INELIGIBLE = 'INELIGIBLE', 'Ineligible'
        EWAF_READY = 'EWAF_READY', 'EWAF Ready'
        EWAF_PROCESSED = 'EWAF_PROCESSED', 'EWAF Processed'
        RANKED = 'RANKED', 'Ranked'
        SELECTED = 'SELECTED', 'Selected'
        WAITLISTED = 'WAITLISTED', 'Waitlisted'
        NOT_SELECTED = 'NOT_SELECTED', 'Not Selected'
        COMPLETED = 'COMPLETED', 'Completed'
        CLOSED = 'CLOSED', 'Closed'

    reference = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_reference = models.CharField(max_length=40, unique=True, editable=False)
    status_token = models.CharField(max_length=64, unique=True, default=status_token, editable=False)
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='applications')
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='program_applications')
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING_PHOTO_VERIFICATION, db_index=True)
    legacy_status = models.CharField(max_length=32, blank=True, editable=False)
    source_snapshot = models.JSONField(default=dict, editable=False)
    current_photo = models.ForeignKey('ApplicationPhoto', null=True, blank=True, on_delete=models.PROTECT, related_name='+', editable=False)
    requirements_snapshot = models.JSONField(default=list)
    program_snapshot = models.JSONField(default=dict)
    answers = models.JSONField(default=dict)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if self._state.adding and not self.public_reference:
            raise ValidationError('Application references must be allocated by the submission service.')
        if not self._state.adding:
            original = type(self).objects.filter(pk=self.pk).values('public_reference', 'status_token').first()
            if original and any(original[name] != getattr(self, name) for name in original):
                raise ValidationError('Application reference and status access token are immutable.')
        return super().save(*args, **kwargs)

    @property
    def current_status(self):
        return self.get_status_display()

    class Meta:
        ordering = ['submitted_at', 'pk']
        default_permissions = ('view', 'change')
        constraints = [models.UniqueConstraint(fields=['program', 'member'], name='one_program_application_per_member'),
                       models.CheckConstraint(condition=models.Q(status__in=['PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED', 'VERIFICATION_FAILED', 'NEEDS_INFORMATION', 'ELIGIBILITY_REVIEW', 'ELIGIBLE', 'INELIGIBLE', 'EWAF_READY', 'EWAF_PROCESSED', 'RANKED', 'SELECTED', 'WAITLISTED', 'NOT_SELECTED', 'COMPLETED', 'CLOSED']), name='program_application_valid_status')]

    @property
    def responses(self):
        return [(item, self.answers.get(str(item['id']), '')) for item in self.requirements_snapshot if item['kind'] != 'document']

    @property
    def original_details(self):
        labels = {'name': 'Program', 'registration_opens_at': 'Applications open',
                  'registration_closes_at': 'Applications close', 'starts_at': 'Program starts',
                  'ends_at': 'Program ends', 'slots': 'Planned beneficiary slots', 'amount': 'Amount per beneficiary (PHP)'}
        details = []
        for name, value in self.program_snapshot.items():
            label = labels.get(name, name.replace('_', ' ').capitalize())
            if name.endswith('_at') and value:
                parsed = parse_datetime(value)
                if parsed:
                    value = format_date(timezone.localtime(parsed), 'M j, Y, g:i A') + ' (Philippine time)'
            details.append((label, value if value not in (None, '') else 'Not specified'))
        return details


def program_document_path(instance, filename):
    return f'programs/{instance.application_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class ProgramDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(ProgramApplication, on_delete=models.PROTECT, related_name='documents')
    requirement = models.ForeignKey(ProgramRequirement, on_delete=models.PROTECT)
    label = models.CharField(max_length=200)
    file = models.FileField(upload_to=program_document_path, max_length=250)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    source_document = models.ForeignKey('documents.MembershipApplicationDocument', null=True, blank=True, on_delete=models.PROTECT)
    source_verification = models.ForeignKey('documents.DocumentVerification', null=True, blank=True, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        constraints = [models.UniqueConstraint(fields=['application', 'requirement'], name='one_program_document_per_requirement')]


class ProgramLog(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='history')
    application = models.ForeignKey(ProgramApplication, null=True, blank=True, on_delete=models.PROTECT, related_name='history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=40)
    notes = models.TextField(max_length=2000)
    changes = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    @property
    def display_changes(self):
        def readable(value):
            if not isinstance(value, dict):
                return value
            labels = {'label': 'Label', 'kind': 'Response type', 'instructions': 'Instructions',
                      'is_required': 'Required', 'is_active': 'Active', 'position': 'Display order'}
            parts = []
            for key, label in labels.items():
                if key in value:
                    detail = value[key]
                    if isinstance(detail, bool):
                        detail = 'Yes' if detail else 'No'
                    elif key == 'kind':
                        detail = dict(ProgramRequirement.Kind.choices).get(detail, detail)
                    parts.append(f'{label}: {detail}')
            return '; '.join(parts) if parts else str(value)
        changes = self.changes if isinstance(self.changes, dict) else {'details': self.changes}
        return [(str(name).replace('_', ' ').capitalize(),
                 {side: readable(value) for side, value in
                  (change if isinstance(change, dict) and ('before' in change or 'after' in change)
                   else {'before': '', 'after': change}).items()})
                for name, change in changes.items()]

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)


class PDAOApprovalRecordQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('PDAO approval history cannot be overwritten. Record a new entry.')

    def delete(self):
        raise ValidationError('PDAO approval history cannot be deleted.')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Use the audited PDAO recording service.')

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError('PDAO approval history cannot be overwritten. Record a new entry.')


class PDAOApprovalRecord(models.Model):
    class Kind(models.TextChoices):
        OFFICIAL = 'official', 'Official approval record — physical letter held'
        LEGACY = 'legacy', 'Legacy Association attestation — physical letter missing'

    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='pdao_approval_records')
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    program_version_at_recording = models.PositiveIntegerField(editable=False)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    approval_date = models.DateField(null=True, blank=True)
    signatory = models.CharField(max_length=200, blank=True)
    manual_confirmation = models.BooleanField(default=False)
    reason = models.TextField(max_length=2000)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', editable=False)
    recorded_by_label = models.CharField(max_length=150, editable=False)
    recorded_at = models.DateTimeField(auto_now_add=True)
    audit_entry = models.OneToOneField(ProgramLog, on_delete=models.PROTECT, related_name='pdao_record', editable=False)
    objects = PDAOApprovalRecordQuerySet.as_manager()

    class Meta:
        ordering = ['-version']
        default_permissions = ('view',)
        permissions = [('record_pdaoapprovalrecord', 'Can record manual PDAO approvals and legacy attestations')]
        constraints = [
            models.UniqueConstraint(fields=['program', 'version'], name='pdao_unique_program_version'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='pdao_positive_version'),
            models.CheckConstraint(condition=models.Q(manual_confirmation=True), name='pdao_manual_confirmation'),
            models.CheckConstraint(condition=models.Q(kind='legacy') | (
                models.Q(kind='official', approval_date__isnull=False) & ~models.Q(signatory='')),
                name='pdao_record_kind_metadata'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if not self.manual_confirmation:
            errors['manual_confirmation'] = 'Explicitly confirm that manual PDAO approval was obtained.'
        if self.kind == self.Kind.OFFICIAL:
            if not self.approval_date:
                errors['approval_date'] = 'Enter the approval date from the physical letter.'
            if not self.signatory.strip():
                errors['signatory'] = 'Enter the signatory from the physical letter.'
        if self.approval_date and self.approval_date > timezone.localdate():
            errors['approval_date'] = 'An approval already obtained cannot have a future date.'
        if not self.reason.strip():
            errors['reason'] = 'Explain this entry, including any correction or missing-letter circumstances.'
        if self.audit_entry_id:
            audit = ProgramLog.objects.filter(pk=self.audit_entry_id).values('program_id', 'actor_id', 'action').first()
            if not audit or (audit['program_id'], audit['actor_id'], audit['action']) != (
                    self.program_id, self.recorded_by_id, 'pdao_recorded'):
                errors['audit_entry'] = 'The audit entry must match this program, recording actor and PDAO recording action.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('PDAO approval history cannot be overwritten. Record a new entry.')
        # Force insertion even if a caller forges an existing primary key.
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('PDAO approval history cannot be deleted.')


class ProgramTermsLock(models.Model):
    """Technical mutex, created lazily; carries no approval or business state."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)

    class Meta:
        default_permissions = ()


class ImmutableTermsArtifact(models.Model):
    objects = PDAOApprovalRecordQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Terms and approval bindings are immutable. Previous entries must be preserved.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Terms and approval bindings cannot be deleted.')

    def validate_audit(self, action):
        if not self.audit_entry_id:
            raise ValidationError('A matching audit entry is required.')
        audit = ProgramLog.objects.filter(pk=self.audit_entry_id).values('program_id', 'actor_id', 'action').first()
        if not audit or (audit['program_id'], audit['actor_id'], audit['action']) != (self.program_id, self.actor_id, action):
            raise ValidationError('The audit must match the program, actor and action.')


class ProgramTermsRevision(ImmutableTermsArtifact):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='terms_revisions')
    number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    schema_version = models.PositiveSmallIntegerField(default=1)
    snapshot = models.JSONField()
    digest = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=2000)
    audit_entry = models.OneToOneField(ProgramLog, on_delete=models.PROTECT, related_name='+')

    class Meta:
        ordering = ['-number']
        default_permissions = ('view',)
        constraints = [models.UniqueConstraint(fields=['program', 'number'], name='unique_program_terms_number'),
                       models.CheckConstraint(condition=models.Q(number__gte=1), name='positive_program_terms_number')]

    def clean(self):
        from .terms import terms_digest, SCHEMA_VERSION, PROGRAM_FIELDS, REQUIREMENT_FIELDS, EVENT_FIELDS
        self.validate_audit('terms_recorded')
        if (self.schema_version != SCHEMA_VERSION or not isinstance(self.snapshot, dict) or
                self.snapshot.get('schema') != SCHEMA_VERSION or self.snapshot.get('program_id') != str(self.program_id) or
                self.digest != terms_digest(self.snapshot)):
            raise ValidationError('The canonical terms and digest must match this program and schema.')
        expected = {'schema', 'program_id', 'program', 'requirements', 'disability_qualifications', 'event'}
        if (set(self.snapshot) != expected or set(self.snapshot['program']) != set(PROGRAM_FIELDS) or
                any(set(item) != {*REQUIREMENT_FIELDS, 'document_type'} for item in self.snapshot['requirements']) or
                any(set(item) != {'id', 'name', 'is_active'} for item in self.snapshot['disability_qualifications']) or
                (self.snapshot['event'] is not None and set(self.snapshot['event']) != {'id', *EVENT_FIELDS})):
            raise ValidationError('The snapshot must use exactly the protected schema fields; budgets and private data are excluded.')
        if not self.reason.strip():
            raise ValidationError('A recording reason is required.')


class ProgramApprovalBinding(ImmutableTermsArtifact):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='approval_bindings')
    revision = models.ForeignKey(ProgramTermsRevision, on_delete=models.PROTECT, related_name='bindings')
    approval_record = models.ForeignKey(PDAOApprovalRecord, on_delete=models.PROTECT, related_name='bindings')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=2000)
    confirmed = models.BooleanField(default=False)
    audit_entry = models.OneToOneField(ProgramLog, on_delete=models.PROTECT, related_name='+')

    class Meta:
        ordering = ['-pk']
        default_permissions = ('view',)
        permissions = [('bind_programapprovalbinding', 'Can review program terms and explicitly bind PDAO approval')]
        constraints = [models.CheckConstraint(condition=models.Q(confirmed=True), name='binding_explicit_confirmation')]

    def clean(self):
        self.validate_audit('approval_bound')
        if not self.confirmed or not self.reason.strip():
            raise ValidationError('Explicit confirmation and a reason are required.')
        if (not self.revision_id or not self.approval_record_id or
                self.revision.program_id != self.program_id or self.approval_record.program_id != self.program_id):
            raise ValidationError('The revision and approval record must belong to this program.')


class ProgramApprovalControl(models.Model):
    program = models.OneToOneField(Program, on_delete=models.PROTECT, related_name='approval_control', primary_key=True)
    current_revision = models.ForeignKey(ProgramTermsRevision, null=True, on_delete=models.PROTECT, related_name='+')
    current_digest = models.CharField(max_length=64, blank=True)
    active_binding = models.ForeignKey(ProgramApprovalBinding, null=True, on_delete=models.PROTECT, related_name='+')
    version = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()


class ProgramDocumentRevision(models.Model):
    document = models.ForeignKey(ProgramDocument, on_delete=models.PROTECT, related_name='revisions')
    file = models.FileField(max_length=250)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    source_document = models.ForeignKey('documents.MembershipApplicationDocument', null=True, on_delete=models.PROTECT)
    source_verification = models.ForeignKey('documents.DocumentVerification', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    reason = models.TextField(max_length=2000)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        ordering = ['-recorded_at', '-pk']


class VerificationWindow(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()


class ProgramCodeCounter(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    value = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()


class ReferenceCounter(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT)
    year = models.PositiveSmallIntegerField()
    value = models.PositiveBigIntegerField(default=0)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['program', 'year'], name='one_reference_counter_program_year')]


def application_photo_path(instance, filename):
    return f'program-photos/{instance.application_id}/{uuid.uuid4().hex}.png'


class ApplicationPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(ProgramApplication, on_delete=models.PROTECT, related_name='photos')
    file = models.FileField(upload_to=application_photo_path, max_length=250)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    member_version = models.PositiveIntegerField()
    reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        default_permissions = ('view',)
        permissions = [('review_applicationphoto', 'Can manually verify application calendar photos'),
                       ('resubmit_applicationphoto', 'Can accept Help Desk application corrections')]


class PhotoVerification(models.Model):
    class Outcome(models.TextChoices):
        PENDING = 'PENDING', 'Pending Photo Verification'
        VERIFIED = 'VERIFIED', 'Verified'
        REJECTED = 'REJECTED', 'Rejected / Verification Failed'
        NEEDS_RESUBMISSION = 'NEEDS_RESUBMISSION', 'Needs Resubmission'

    photo = models.ForeignKey(ApplicationPhoto, on_delete=models.PROTECT, related_name='reviews')
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    reason = models.TextField(max_length=2000)
    category = models.CharField(max_length=120, blank=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reviewer_label = models.CharField(max_length=150)
    member_version = models.PositiveIntegerField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        ordering = ['-reviewed_at', '-pk']


from .decision_email_models import ApplicationDecisionEmail, ApplicationDecisionEmailAttempt  # noqa: F401,E402
