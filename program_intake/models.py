import uuid
from django.conf import settings
from django.db import models
from ewaf.models import EvidenceArtifact


class ApplicationCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT)
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, unique=True)
    member_version = models.PositiveIntegerField()
    program_version = models.PositiveIntegerField()
    authority = models.JSONField()
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    reason = models.TextField()
    redeemed_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    grant_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        permissions = [('issue_applicationcode', 'Issue a program application code after onsite identity verification')]


class SocioeconomicReview(EvidenceArtifact):
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT)
    document = models.ForeignKey('programs.ProgramDocument', on_delete=models.PROTECT)
    configuration = models.ForeignKey('ewaf.OperationalConfiguration', on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=16, choices=[('VERIFIED', 'Verified'), ('DISPUTED', 'Disputed'), ('REJECTED', 'Rejected')])
    value = models.JSONField(null=True, blank=True)
    observation_start = models.DateField()
    observation_end = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    source = models.JSONField()

    class Meta:
        default_permissions = ('view',)
        ordering = ['-revision', '-pk']
        constraints = [models.UniqueConstraint(fields=['application', 'revision'], name='intake_si_review_revision')]
        permissions = [('review_socioeconomic', 'Review submitted program socioeconomic evidence')]

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if (self.application.program_id != self.program_id or self.document.application_id != self.application_id
                or self.configuration.program_id != self.program_id):
            raise ValidationError('The review, document and configuration must belong to this application’s program.')
        if self.previous_id and (self.previous.application_id, self.previous.revision) != (self.application_id, self.revision - 1):
            raise ValidationError('Retain the immediately preceding socioeconomic review.')
        if not self.previous_id and self.revision != 1:
            raise ValidationError('Later reviews require a predecessor.')
