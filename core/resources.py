"""Public guidance reads published CMS snapshots only; no personal-data collection."""
from django.http import Http404
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from .content import DEFAULTS, RESOURCE_KEYS, published_content
from .models import PublicContent


@never_cache
@require_safe
def index(request):
    published = {row.key: row.published for row in PublicContent.objects.filter(key__in=RESOURCE_KEYS)
                 if row.published}
    return render(request, 'public/resources/index.html', {'sections': [
        {'key': key, 'title': DEFAULTS[key][0], 'published': published.get(key)} for key in RESOURCE_KEYS
        if key != 'resources-verification'], 'verification': published.get('resources-verification'),
        'referrals_enabled': getattr(settings, 'REFERRAL_ENABLED', False),
        'contact_content': published_content('contact')})


@never_cache
@require_safe
def detail(request, key):
    if key not in RESOURCE_KEYS:
        raise Http404
    item = PublicContent.objects.filter(key=key).first()
    if not item or not item.published:
        raise Http404('Reviewed information is unavailable.')
    return render(request, 'public/resources/detail.html', {'resource': item.published, 'resource_key': key})
