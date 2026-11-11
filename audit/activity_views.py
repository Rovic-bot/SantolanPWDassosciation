"""Private, read-only views for the combined administration history."""
from datetime import timedelta

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_safe

from .activity import AREAS, FIELDS, KINDS, combine, filtered_queries, permitted_sources
from .activity_notes import readable_notes
from .admin_presentation import AuditDateForm


class ActivityFilters(AuditDateForm):
    field_order = ('q', 'area', 'activity', 'actor', 'date_from', 'date_to')
    q = forms.CharField(required=False, max_length=200, label='Search activity',
                        widget=forms.TextInput(attrs={'type': 'search', 'placeholder': 'Action, member, program, or admin'}))
    area = forms.ChoiceField(required=False, label='Section')
    activity = forms.ChoiceField(required=False, label='Action')
    actor = forms.ChoiceField(required=False, label='Administrator')
    kind = forms.ChoiceField(required=False, label='Action type',
        choices=[('', 'All types')] + [(key, value[1]) for key, value in KINDS.items()],
        widget=forms.RadioSelect)
    period = forms.ChoiceField(required=False, label='Time range', choices=[
        ('', 'All time'), ('today', 'Today'), ('7', 'Last 7 days'),
        ('30', 'Last 30 days'), ('90', 'Last 90 days'), ('custom', 'Custom dates')])

    def __init__(self, data, sources):
        data = data.copy()
        if not data.get('period') and (data.get('date_from') or data.get('date_to')):
            data['period'] = 'custom'
        if data.get('period') not in ('', 'custom', None):
            data['date_from'] = data['date_to'] = ''
        super().__init__(data)
        queries = [source.queryset() for source in sources]
        labels = list(combine(queries, ('activity_label', 'activity_area'), distinct=True).order_by('activity_label'))
        areas = {row['activity_area'] for row in labels}
        self.fields['area'].choices = [('', 'All sections')] + [
            (key, label) for key, label in AREAS.items() if key in areas]
        self.fields['activity'].choices = [('', 'All actions')] + [
            (label, label) for label in sorted({row['activity_label'] for row in labels})]
        actors = combine(queries, ('activity_actor',), distinct=True).order_by('activity_actor')
        self.fields['actor'].choices = [('', 'All administrators')] + [
            (row['activity_actor'], row['activity_actor']) for row in actors]

    def clean(self):
        values = super().clean()
        period = values.get('period')
        if period in ('today', '7', '30', '90'):
            days = 1 if period == 'today' else int(period)
            values['date_to'] = timezone.localdate()
            values['date_from'] = values['date_to'] - timedelta(days=days - 1)
        return values


def context_for(request, model_admin):
    if not model_admin.has_view_permission(request):
        raise PermissionDenied
    return {**model_admin.admin_site.each_context(request), 'opts': model_admin.model._meta,
            'title': 'Administration changes', 'media': model_admin.media}


def decorate(row):
    label, _, icon = KINDS[row['activity_kind']]
    return {**row, 'area_label': AREAS[row['activity_area']],
            'kind_label': label, 'icon': icon,
            'detail_url': reverse('admin:administration_activity',
                                  args=[row['activity_source'], row['activity_id']])}


@require_safe
def activity_list(request, model_admin):
    context = context_for(request, model_admin)
    sources = permitted_sources(request.user)
    form = ActivityFilters(request.GET, sources)
    queries = list(filtered_queries(sources, form.cleaned_data)) if form.is_valid() else []
    results = combine(queries).order_by('-activity_time', 'activity_source', '-activity_id') if queries else []
    page = Paginator(results, 30).get_page(request.GET.get('p'))
    page.object_list = [decorate(row) for row in page.object_list]

    def category_url(kind):
        query = request.GET.copy()
        query.pop('p', None)
        query.pop('kind', None)
        if kind:
            query['kind'] = kind
        return '?' + query.urlencode() if query else request.path

    metrics = [{'label': 'Recorded actions', 'value': page.paginator.count,
                'hint': 'Matching the current filters', 'kind': 'change', 'icon': 'activity'}]
    for kind, label, hint in [('approval', 'Approvals', 'Recorded approval actions'),
                             ('access', 'Documents & prints', 'Recorded access and exports'),
                             ('publication', 'Publications', 'Published programs and updates')]:
        total = combine([query.filter(activity_kind=kind) for query in queries]).count() if queries else 0
        metrics.append({'label': label, 'value': total, 'hint': hint, 'kind': kind, 'icon': KINDS[kind][2]})
    for metric in metrics:
        metric['display_value'] = f"{metric['value']:,}"

    def page_url(number):
        query = request.GET.copy()
        query['p'] = number
        return '?' + query.urlencode()

    context.update(form=form, page=page, metrics=metrics,
        tabs=[{'label': label, 'url': category_url(kind), 'active': request.GET.get('kind', '') == kind}
              for kind, label in [('', 'All activity'), ('approval', 'Approvals'),
                                  ('access', 'Documents & prints'), ('publication', 'Publications')]],
        active_filter_count=sum(bool(request.GET.get(key)) for key in ('q', 'area', 'activity', 'actor', 'kind'))
                            + int(any(request.GET.get(key) for key in ('period', 'date_from', 'date_to'))),
        previous_url=page_url(page.previous_page_number()) if page.has_previous() else '',
        next_url=page_url(page.next_page_number()) if page.has_next() else '',
        page_links=[{'number': number, 'url': page_url(number) if isinstance(number, int) else ''}
                    for number in page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)])
    return render(request, 'admin/audit/activity_list.html', context)


@require_safe
def activity_detail(request, model_admin, source, pk):
    context = context_for(request, model_admin)
    specification = next((item for item in permitted_sources(request.user) if item.key == source), None)
    if specification is None:
        raise Http404
    try:
        query = specification.queryset().filter(pk=pk)
        item = query.first()
        if item is None:
            raise Http404
        row = decorate(query.values(*FIELDS).get())
    except (ValueError, ValidationError):
        raise Http404
    popup = request.GET.get('dialog') == '1'
    context.update(activity=row, **readable_notes(item, specification, row), original_model=specification.model, popup=popup,
                   title=row['activity_label'])
    return render(request, 'admin/audit/activity_content.html' if popup else 'admin/audit/activity_detail.html', context)
