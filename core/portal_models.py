"""Versioned public-page copy and artwork, independent of program records."""
from django.conf import settings
from django.db import models


class PortalPage(models.Model):
    key = models.SlugField(primary_key=True, max_length=32)
    content = models.JSONField(default=dict)
    published = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        default_permissions = ()


class PortalPageRevision(models.Model):
    page = models.ForeignKey(PortalPage, on_delete=models.PROTECT, related_name='revisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    version = models.PositiveIntegerField()
    action = models.CharField(max_length=20)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['-occurred_at', '-pk']
        constraints = [models.UniqueConstraint(fields=('page', 'version'), name='unique_portal_page_revision')]
