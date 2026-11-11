"""Read-only audit list filters and presentation context."""
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, time

from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.utils import timezone


class AuditDateForm(forms.Form):
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        values = super().clean()
        if values.get('date_from') and values.get('date_to') and values['date_from'] > values['date_to']:
            raise forms.ValidationError('Start date must be on or before end date.')
        return values


class AuditDateFilter(admin.SimpleListFilter):
    title = 'date range'
    parameter_name = 'date_from'

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        if 'date_to' in params:
            self.used_parameters['date_to'] = params.pop('date_to')[-1]
        self.date_field = model_admin.audit_date_field

    def expected_parameters(self):
        return ['date_from', 'date_to']

    def lookups(self, request, model_admin):
        return ()

    def has_output(self):
        return True

    def queryset(self, request, queryset):
        form = AuditDateForm(self.used_parameters)
        if not form.is_valid():
            return queryset.none()
        for key, lookup in [('date_from', 'gte'), ('date_to', 'lte')]:
            if form.cleaned_data.get(key):
                boundary = timezone.make_aware(datetime.combine(form.cleaned_data[key],
                    time.max if key == 'date_to' else time.min))
                queryset = queryset.filter(**{f'{self.date_field}__{lookup}': boundary})
        return queryset


class AuditListPresentation:
    show_facets = admin.ShowFacets.ALWAYS
    list_per_page = 30

    def changelist_view(self, request, extra_context=None):
        empty_filters = [key for key in ('action__exact', 'action_flag__exact',
            'user__id__exact', 'content_type__id__exact') if key in request.GET and not request.GET[key]]
        if request.method == 'GET' and empty_filters:
            query = request.GET.copy()
            for key in empty_filters:
                query.pop(key)
            return HttpResponseRedirect(request.path + ('?' + query.urlencode() if query else ''))
        response = super().changelist_view(request, extra_context=extra_context)
        if not getattr(response, 'context_data', None) or 'cl' not in response.context_data:
            return response
        cl = response.context_data['cl']
        filters = []
        excluded = {'p', 'date_from', 'date_to'}
        for spec in cl.filter_specs:
            excluded.update(spec.expected_parameters())
            if isinstance(spec, AuditDateFilter):
                continue
            parameter = spec.expected_parameters()[0]
            options = []
            for choice in spec.choices(cl):
                parameters = parse_qs(urlsplit(choice['query_string']).query)
                if any(key in parameters for key in spec.expected_parameters()[1:]):
                    continue
                value = parameters.get(parameter, [''])[0]
                options.append({**choice, 'value': value})
            filters.append({'name': parameter, 'title': spec.title, 'options': options,
                'radio': parameter in ('action__exact', 'action_flag__exact')})
        response.context_data.update({
            'audit_filters': filters,
            'audit_preserved_filters': [(key, value) for key, values in request.GET.lists()
                if key not in excluded for value in values],
            'audit_dates': AuditDateForm(request.GET),
        })
        return response
