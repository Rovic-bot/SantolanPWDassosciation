"""Private review preparation, separate from accepted evidence and decisions."""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

_writing = ContextVar('information_review_writer', default=False)


@contextmanager
def review_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class ReviewQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the private review service.')

    def delete(self):
        raise PermissionDenied('Review disposal requires an approved procedure.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the private review service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the private review service.')


class ReviewRecord(models.Model):
    objects = ReviewQuerySet.as_manager()
    append_only = False

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get() or (self.append_only and not self._state.adding):
            raise PermissionDenied('Use the private review service; retain original history.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Review disposal requires an approved procedure.')


class InformationReview(ReviewRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True, editable=False)
    payload_digest = models.CharField(max_length=64, editable=False)
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='information_reviews')
    application = models.ForeignKey('programs.ProgramApplication', null=True, blank=True, on_delete=models.PROTECT, related_name='information_reviews')
    kind = models.CharField(max_length=16, choices=[('information', 'Information review'), ('evaluation', 'Evaluation clarification')])
    trigger = models.CharField(max_length=24, choices=[('reported_change', 'Reported change'), ('outdated', 'Outdated evidence'), ('discrepancy', 'Material inconsistency'), ('routine', 'Authorized routine check'), ('clarification', 'Applicant clarification')])
    declaration = models.CharField(max_length=16, choices=[('not_collected', 'Not collected'), ('no_change', 'Applicant reports no change'), ('changes', 'Applicant reports changes'), ('uncertain', 'Applicant is uncertain')])
    concern = models.TextField(max_length=2000)
    identity_basis = models.TextField(max_length=2000)
    policy_snapshot = models.JSONField(editable=False)
    state = models.CharField(max_length=24, default='received', choices=[('received', 'Received'), ('under_review', 'Under review'), ('needs_information', 'Needs information'), ('findings_recorded', 'Findings recorded; source action pending')])
    version = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        default_permissions = ('view',)
        permissions = [('record_informationreview', 'Can record authorized private review concerns and findings')]
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=['information', 'evaluation']), name='info_review_kind'),
            models.CheckConstraint(condition=~models.Q(kind='evaluation') | models.Q(application__isnull=False), name='evaluation_review_application'),
            models.CheckConstraint(condition=models.Q(state__in=['received', 'under_review', 'needs_information', 'findings_recorded']), name='info_review_state'),
        ]


class InformationReviewAction(ReviewRecord):
    append_only = True
    review = models.ForeignKey(InformationReview, on_delete=models.PROTECT, related_name='actions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=24)
    reason = models.TextField(max_length=2000)
    previous_values = models.TextField(max_length=2000, blank=True)
    reported_values = models.TextField(max_length=2000, blank=True)
    findings = models.TextField(max_length=2000, blank=True)
    observed_on = models.DateField(null=True, blank=True)
    effective_on = models.DateField(null=True, blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['occurred_at', 'pk']
        default_permissions = ()
