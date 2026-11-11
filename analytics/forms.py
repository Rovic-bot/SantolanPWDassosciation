"""Date-only dashboard filters, interpreted in the configured application timezone."""
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from django import forms
from django.utils import timezone
from programs.models import Program


def months_before(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


class ActivityRangeForm(forms.Form):
    period = forms.ChoiceField(label='Activity period', choices=[
        ('six_months', 'Last 6 months'), ('30_days', 'Last 30 days'),
        ('year', 'This year'), ('custom', 'Custom range')],
        widget=forms.Select(attrs={'class': 'form-select'}))
    program = forms.ModelChoiceField(label='Program', queryset=Program.objects.none(), required=False,
        empty_label='All programs', widget=forms.Select(attrs={'class': 'form-select', 'aria-describedby': 'range-help'}))
    start = forms.DateField(required=False, label='Start date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'aria-describedby': 'range-help'}))
    end = forms.DateField(required=False, label='End date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'aria-describedby': 'range-help'}))

    def __init__(self, data=None, *, today=None, user=None, **kwargs):
        self.today = today or timezone.localdate()
        if data is not None and data.get('period', 'six_months') != 'custom':
            data = data.copy()
            data['period'] = data.get('period') or 'six_months'
            data['start'], data['end'] = '', ''
        super().__init__(data, **kwargs)
        if user and user.is_active and user.is_staff and user.has_perms(('accounts.access_dashboard', 'programs.view_program')):
            self.fields['program'].queryset = Program.objects.only('pk', 'name').order_by('name', 'pk')

    def clean(self):
        values = super().clean()
        period = values.get('period')
        if period != 'custom':
            values['end'] = self.today
            values['start'] = {'six_months': months_before(self.today, 5).replace(day=1),
                               '30_days': self.today - timedelta(days=29),
                               'year': self.today.replace(month=1, day=1)}.get(period)
        start, end = values.get('start'), values.get('end')
        if not start or not end:
            if period == 'custom':
                raise forms.ValidationError('Enter both dates for a custom range.')
            return values
        if start > end:
            raise forms.ValidationError('The end date must be on or after the start date.')
        if (end - start).days > 730:
            raise forms.ValidationError('Choose a range of 731 days or fewer.')
        if start.year < 1900 or end.year > 2100:
            raise forms.ValidationError('Choose dates between 1900 and 2100.')
        # Future dates are useful for scheduled events; no future activity is inferred.
        zone = timezone.get_default_timezone()
        values['lower'] = timezone.make_aware(datetime.combine(start, time.min), zone)
        values['upper'] = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), zone)
        return values
