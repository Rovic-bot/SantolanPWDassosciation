from calendar import month_name, monthrange
from datetime import date

from django import forms
from django.conf import settings
from django.utils import timezone

from announcements.images import prepare_image
from membership.forms import StyledForm
from .models import AnnualObservance
from .participation import TARGET_HELP


class AnnualObservanceForm(StyledForm, forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(label='Reason for this change', max_length=2000,
                           widget=forms.Textarea(attrs={'rows': 2}))
    month = forms.TypedChoiceField(coerce=int, choices=[(i, month_name[i]) for i in range(1, 13)])
    image = forms.FileField(label='Photo', required=False,
                           widget=forms.FileInput(attrs={'accept': '.png,.jpg,.jpeg'}))
    remove_image = forms.BooleanField(label='Remove the current photo', required=False)

    class Meta:
        model = AnnualObservance
        fields = ('title', 'target_audience', 'who_may_participate', 'month', 'category', 'recurrence_kind', 'day_start', 'day_end',
                  'legal_basis', 'source_url', 'description', 'image', 'image_alt')
        labels = {'legal_basis': 'Legal basis / official reference', 'category': 'Observance subject', 'recurrence_kind': 'Annual recurrence', 'day_start': 'Day of month / first day',
                  'day_end': 'Last day of range', 'image_alt': 'Photo description'}
        widgets = {'description': forms.Textarea(attrs={'rows': 5}),
                   'target_audience': forms.Textarea(attrs={'rows': 2}),
                   'who_may_participate': forms.Textarea(attrs={'rows': 3})}
        help_texts = {
            'target_audience': TARGET_HELP,
            'who_may_participate': 'State who may join related activities under the organizer\'s rules. An annual observance alone does not schedule an Association activity. Required before publication.',
            'day_start': 'Only for a fixed day or fixed range. Leave blank for other annual recurrence rules.',
            'day_end': 'Only for a fixed range in the same month. Leave blank otherwise.',
            'recurrence_kind': 'Third week stays descriptive; no exact dates are inferred for a particular year.',
            'source_url': 'Direct HTTPS source from NCDA, the Senate reference library, the United Nations or the official GAAD website.',
            'image_alt': 'Required with a photo. Include essential poster information in the description too.',
        }

    def __init__(self, *args, publishing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['version'] = 0 if self.instance._state.adding else self.instance.version
        if publishing:
            for field in ('target_audience', 'who_may_participate'):
                self.fields[field].required = True
        self.style_fields()
        self.fields['remove_image'].widget.attrs['class'] = 'form-check-input'

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'content_type'):
            return prepare_image(image, max_bytes=settings.EVENT_IMAGE_MAX_BYTES,
                                 max_pixels=settings.EVENT_IMAGE_MAX_PIXELS)
        return image

    def clean(self):
        cleaned = super().clean()
        if self.cleaned_data.get('remove_image'):
            if self.files.get('image'):
                self.add_error('image', 'Choose replacement or removal, not both.')
            else:
                cleaned['image'] = False
                cleaned['image_alt'] = ''
        if any(key != 'image' or len(self.files.getlist(key)) != 1 for key in self.files):
            self.add_error(None, 'Upload one photo only.')
        return cleaned


class AnnualObservanceEditForm(AnnualObservanceForm):
    """Shared compact authoring; omitted existing metadata stays on the record."""
    start_date = forms.DateField(label='Start date', required=False,
                                widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    end_date = forms.DateField(label='End date', required=False,
                              widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('month', 'category', 'recurrence_kind', 'day_start', 'day_end',
                     'legal_basis', 'source_url', 'who_may_participate', 'image_alt', 'notes'):
            self.fields.pop(name)
        self.fields['target_audience'].required = True
        self.fields['target_audience'].help_text = ''
        self.fields['image'].label = 'Image'
        self.fields['remove_image'].label = 'Remove the current image'
        creating = self.instance._state.adding
        self.current_schedule = self.instance.recurrence_rule or 'Choose start and end dates'
        self.original_dates = None
        kind = self.instance.recurrence_kind
        if not creating and kind in ('fixed_day', 'fixed_range', 'whole_month'):
            year, month = timezone.localdate().year, self.instance.month
            start = 1 if kind == 'whole_month' else self.instance.day_start
            end = (monthrange(year, month)[1] if kind == 'whole_month'
                   else self.instance.day_end or start)
            # A February 29 reference remains editable even during a non-leap year.
            if month == 2 and end == 29 and monthrange(year, month)[1] < 29:
                year = next(candidate for candidate in range(year + 1, year + 5)
                            if monthrange(candidate, 2)[1] == 29)
            self.initial.update(start_date=date(year, month, start), end_date=date(year, month, end))
            self.original_dates = ((month, start), (month, end))
            self.fields['start_date'].required = self.fields['end_date'].required = True
        if creating:
            self.fields['start_date'].required = self.fields['end_date'].required = True
            self.fields.pop('remove_image')
        self.order_fields(('title', 'target_audience', 'start_date', 'end_date',
                           'description', 'image', 'remove_image', 'version'))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if bool(start) != bool(end):
            self.add_error('end_date' if start else 'start_date', 'Choose both the start and end dates.')
        elif start and end:
            if start.month != end.month:
                self.add_error('end_date', 'Choose an end date in the same observance month.')
            elif end.day < start.day:
                self.add_error('end_date', 'The end date must be on or after the start date.')
            elif ((start.month, start.day), (end.month, end.day)) != self.original_dates:
                cleaned.update(month=start.month, day_start=start.day,
                               day_end=end.day if end.day != start.day else None,
                               recurrence_kind='fixed_range' if end.day != start.day else 'fixed_day')
        if 'image' in cleaned:
            if cleaned['image'] is False:
                cleaned['image_alt'] = ''
            elif self.files.get('image'):
                cleaned['image_alt'] = cleaned.get('title', self.instance.title)
        cleaned['notes'] = ('Created annual observance draft in the editor.' if self.instance._state.adding
                            else 'Updated annual observance details in the editor.')
        return cleaned


class ObservancePublicationForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField()
    notes = forms.CharField(label='Reason', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='I have reviewed this content and confirm this publication change.')

    def __init__(self, *args, actions, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = actions
        self.style_fields()
        self.fields['confirm'].widget.attrs['class'] = 'form-check-input'
