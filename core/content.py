from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from django.utils import timezone
from urllib.parse import urlsplit
from accounts.decorators import dashboard_required
from membership.forms import StyledForm
from .models import PublicContent, ContentRevision
from .permissions import require_workspace_permissions
from .about import ABOUT_TITLE, ABOUT_BODY


DEFAULTS = {
    'about': (ABOUT_TITLE, ABOUT_BODY),
    'membership': ('How to Become a Member', 'Read the Association membership guide for available submission channels and confirmed requirements. Onsite verification at the Help Desk and an authorized membership decision remain required.'),
    'contact': ('Contact / Help Desk', 'For membership registration, application corrections or assistance, visit the Barangay Santolan PWD Association Help Desk. Confirm the address, contact details and office hours through the association’s official channels.'),
    'faq': ('Frequently Asked Questions', 'Read the membership guide for available submission channels and onsite instructions. Verified Members apply to available programs without a login. Keep your Application Reference Number and follow official Announcements for results.'),
    'privacy': ('Privacy information', 'Member records, application documents and calendar photos are private. Only authorized Admin personnel may access them for association processing. Public announcements use approved privacy-safe results. Contact the Association Help Desk for the association’s detailed privacy notice and privacy requests.'),
    'accessibility': ('Accessibility help', 'Use the Display controls to adjust text size, high contrast and reduced motion. You can navigate with a keyboard, use browser zoom or your screen reader. To listen to text, highlight it and choose Read aloud, or press Alt + R. Close the reading control or press Escape to end playback. Contact the Association Help Desk if you need help completing an application or taking the required calendar photo.'),
    'ewaf': ('How EWAF works', 'For programs that use EWAF, the system compares the complete eligible applicant pool using the authorized criteria and configuration. AHP-derived weights, Min–Max normalization and a weighted sum support the evaluation. Missing or stale required evidence must be resolved through the approved review process. Authorized personnel record beneficiary decisions subject to capacity and tie controls. Scores cannot be manually edited, and the system does not assign numerical business ranks. Submission, eligibility, evaluation, selection and actual assistance are separate steps. Each program publishes its own approved method; contact the Help Desk for private clarification.'),
    'application-information': ('Application Information / Reference Number guidance', 'Only Verified Members may submit Program Applications. After a successful submission, keep your unique Application Reference Number as proof. Admin manually reviews your calendar photo before final eligibility processing. Submission does not promise selection. Follow official Announcements for results or contact the Barangay Santolan PWD Association Help Desk for assistance.'),
    'home': ('Public Information Portal', 'Browse association information, available programs/events and official announcements. Read the membership guide for available submission channels and required onsite verification.'),
}

RESOURCE_KEYS = tuple(key for key in PublicContent.Key.values if key.startswith('resources-'))
for _key in RESOURCE_KEYS:
    DEFAULTS[_key] = (PublicContent.Key(_key).label, 'Reviewed information will be published here when available. Contact the Association Help Desk for assistance.')


def content_snapshot(item):
    return {'title': item.title, 'body': item.body, 'published': item.published, 'version': item.version,
        'source_url': item.source_url, 'provider': item.provider,
        'reviewed_on': item.reviewed_on.isoformat() if item.reviewed_on else None, 'archived': item.archived}


def current_editor(user, *, publication=False):
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if actor is None:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    require_workspace_permissions(actor, 'core.view_publiccontent', 'core.change_publiccontent',
        *(['core.publish_publiccontent'] if publication else []))
    return actor


def published_content(key):
    item = PublicContent.objects.filter(key=key).first()
    title, body = DEFAULTS[key]
    return item.published if item and item.published else {'title': title, 'body': body}


class ContentForm(StyledForm, forms.Form):
    title = forms.CharField(max_length=200)
    body = forms.CharField(max_length=20000, widget=forms.Textarea(attrs={'rows': 12}),
        help_text='Plain text only. Do not include private member information. Required workflow instructions remain enforced by the system.')
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[('draft', 'Save draft'), ('publish', 'Authorize and publish'), ('withdraw', 'Withdraw published content')])
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    source_url = forms.URLField(max_length=500, required=False, label='Official source URL',
        help_text='Use the reviewed HTTPS source. Do not include private identifiers or credentials in a link.')
    provider = forms.CharField(max_length=200, required=False, label='Responsible office or provider')
    reviewed_on = forms.DateField(required=False, label='Actual source review date', widget=forms.DateInput(attrs={'type': 'date'}))
    source_review_confirmed = forms.BooleanField(required=False,
        label='I reviewed the source, provider and public wording for this publication.')

    def __init__(self, *args, resource=False, **kwargs):
        self.resource = resource
        super().__init__(*args, **kwargs)
        if resource:
            self.fields['action'].choices = [*self.fields['action'].choices, ('archive', 'Archive and withdraw this resource')]
        else:
            for name in ('source_url', 'provider', 'reviewed_on', 'source_review_confirmed'):
                self.fields.pop(name)
        self.style_fields()

    def clean(self):
        values = super().clean()
        if self.resource:
            source = values.get('source_url')
            if source:
                parsed = urlsplit(source)
                if parsed.scheme != 'https' or parsed.username or parsed.password:
                    self.add_error('source_url', 'Use a reviewed HTTPS URL without credentials.')
            if values.get('reviewed_on') and values['reviewed_on'] > timezone.localdate():
                self.add_error('reviewed_on', 'Enter the date the review actually took place.')
            if values.get('action') == 'publish' and not all(values.get(name) for name in (
                    'source_url', 'provider', 'reviewed_on', 'source_review_confirmed')):
                raise ValidationError('Publication requires the official source, responsible provider, actual review date and review confirmation.')
        return values


@transaction.atomic
def save_content(key, *, user, data):
    user = current_editor(user)
    if key not in PublicContent.Key.values:
        raise ValidationError('Choose a supported public information page.')
    form = ContentForm(data, resource=key in RESOURCE_KEYS)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    publication = values['action'] in ('publish', 'withdraw', 'archive')
    if publication:
        user = current_editor(user, publication=True)
    item, _ = PublicContent.objects.get_or_create(key=key, defaults={'title': DEFAULTS[key][0], 'body': DEFAULTS[key][1]})
    item = PublicContent.objects.select_for_update().get(pk=item.pk)
    if item.version != values['version']:
        raise ValidationError('This content changed. Reload before continuing.')
    before = content_snapshot(item)
    item.title, item.body = values['title'], values['body']
    if key in RESOURCE_KEYS:
        for name in ('source_url', 'provider', 'reviewed_on'):
            setattr(item, name, values[name])
    item.version += 1
    item.updated_by = user
    if values['action'] == 'publish':
        item.published = {'title': item.title, 'body': item.body, 'version': item.version}
        item.archived = False
        if key in RESOURCE_KEYS:
            item.published.update(source_url=item.source_url, provider=item.provider, reviewed_on=item.reviewed_on.isoformat())
    elif values['action'] in ('withdraw', 'archive'):
        item.published = {}
        item.archived = values['action'] == 'archive'
    item.save()
    user = current_editor(user, publication=publication)
    ContentRevision.objects.create(content=item, actor=user, actor_label=user.get_username(),
        action=values['action'], reason=values['reason'], before=before,
        after=content_snapshot(item))
    return item


@never_cache
@dashboard_required
@require_safe
def content_list(request):
    require_workspace_permissions(request.user, 'core.view_publiccontent')
    from .portal_editor import editor
    return editor(request)


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def content_edit(request, key):
    require_workspace_permissions(request.user, 'core.view_publiccontent', 'core.change_publiccontent')
    if key not in PublicContent.Key.values:
        from django.http import Http404
        raise Http404
    item = PublicContent.objects.filter(pk=key).first()
    title, body = DEFAULTS[key]
    initial = {'title': item.title if item else title, 'body': item.body if item else body, 'version': item.version if item else 0, 'action': 'draft'}
    if item and key in RESOURCE_KEYS:
        initial.update(source_url=item.source_url, provider=item.provider, reviewed_on=item.reviewed_on)
    form = ContentForm(request.POST if request.method == 'POST' else None, initial=initial, resource=key in RESOURCE_KEYS)
    if key == 'about':
        form.fields['body'].help_text = 'Use ## before a section heading and - before each bullet. Separate headings, paragraphs, and lists with a blank line. Text is displayed safely; HTML is not supported. Do not include private member information.'
    if not request.user.has_perm('core.publish_publiccontent'):
        form.fields['action'].choices = [('draft', 'Save draft')]
    if request.method == 'POST' and form.is_valid():
        try:
            save_content(key, user=request.user, data=request.POST)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Public information saved with audit history.')
            return redirect('core:content_edit', key=key)
    from membership.guidance import membership_guidance
    return render(request, 'content/edit.html', {'form': form, 'title': title, 'content_key': key,
        **(membership_guidance() if key == 'membership' else {}),
        'history': item.revisions.all()[:30] if item and request.user.has_perm('core.view_contentrevision') else []})
