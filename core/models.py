from django.conf import settings
from django.db import models
from .reference_models import ShortReference
from .portal_models import PortalPage, PortalPageRevision


class PublicContent(models.Model):
    class Key(models.TextChoices):
        HOME = 'home', 'Home'
        ABOUT = 'about', 'About the Association'
        MEMBERSHIP = 'membership', 'How to Become a Member'
        CONTACT = 'contact', 'Contact / Help Desk'
        FAQ = 'faq', 'Frequently Asked Questions'
        PRIVACY = 'privacy', 'Privacy information'
        ACCESSIBILITY = 'accessibility', 'Accessibility help'
        EWAF = 'ewaf', 'EWAF explanation'
        APPLICATION = 'application-information', 'Application Information / Reference Number guidance'
        RESOURCE_HELP = 'resources-help', 'Where Can I Get Help?'
        RESOURCE_GUIDES = 'resources-guides', 'PWD ID and Association Membership Guides'
        RESOURCE_RIGHTS = 'resources-rights', 'PWD Rights and Benefits Information'
        RESOURCE_WORK = 'resources-work', 'Employment and Training Opportunities'
        RESOURCE_CARE = 'resources-care', 'Family, Guardian and Caregiver Guidance'
        RESOURCE_EXTERNAL = 'resources-external', 'External Assistance Information'
        RESOURCE_ACCESS = 'resources-accessibility', 'Accessibility Help and Information Feedback'
        RESOURCE_VERIFY = 'resources-verification', 'PWD ID Verification — External Website'

    key = models.CharField(max_length=32, primary_key=True, choices=Key.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=20000)
    published = models.JSONField(default=dict, editable=False)
    version = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    source_url = models.URLField(max_length=500, blank=True)
    provider = models.CharField(max_length=200, blank=True)
    reviewed_on = models.DateField(null=True, blank=True)
    archived = models.BooleanField(default=False, editable=False)

    class Meta:
        default_permissions = ('view', 'change')
        permissions = [('publish_publiccontent', 'Can authorize public information publication')]


class ContentRevision(models.Model):
    content = models.ForeignKey(PublicContent, on_delete=models.PROTECT, related_name='revisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=20)
    reason = models.TextField(max_length=2000)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        ordering = ['-occurred_at', '-pk']
