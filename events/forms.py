from django import forms
from django.conf import settings
from membership.forms import StyledForm
from announcements.images import prepare_image
from members.models import Member
from .models import Event, EventAttendance, EventRegistration
from .participation import TARGET_HELP, PARTICIPATION_HELP, PARTICIPATION_FIELDS, guard_participation


class EventForm(StyledForm, forms.ModelForm):
    def save(self, commit=True):
        from programs.terms import terms_lock, guard_event
        with terms_lock():
            old = Event.objects.filter(pk=self.instance.pk).first() if not self.instance._state.adding else None
            guard_event(old, self.instance)
            guard_participation(old, self.instance)
            return super().save(commit=commit)

    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(required=False, max_length=2000, widget=forms.HiddenInput)
    image = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept': '.png,.jpg,.jpeg'}))
    remove_image = forms.BooleanField(required=False, label='Remove the current image')

    class Meta:
        model = Event
        fields = ('title', 'event_category', 'target_audience', 'who_may_participate', 'description',
                  'location', 'starts_at', 'ends_at', 'capacity', 'image', 'image_alt', 'application_program')
        widgets = {'description': forms.Textarea(attrs={'rows': 7}), **{
            name: forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})
            for name in ('starts_at', 'ends_at')},
            'target_audience': forms.Textarea(attrs={'rows': 2}),
            'who_may_participate': forms.Textarea(attrs={'rows': 3})}
        labels = {'event_category': 'Event category'}
        help_texts = {'capacity': 'Optional venue planning capacity; this is not a public registration requirement.',
                      'target_audience': 'Optional. ' + TARGET_HELP,
                      'who_may_participate': 'Optional. ' + PARTICIPATION_HELP,
                      'event_category': 'General: open to everyone under the organizer\'s rules. Specific: focused on a disability group or observance.'}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('image_alt')
        for name in ('event_category', 'target_audience', 'who_may_participate', 'capacity', 'application_program'):
            self.fields.pop(name, None)
        self.initial['version'] = self.instance.version
        self.style_fields()
        self.fields['remove_image'].widget.attrs['class'] = 'form-check-input'
        for name in ('starts_at', 'ends_at'):
            self.fields[name].help_text = 'Philippine time (Asia/Manila).'
        if not self.instance.image:
            self.fields.pop('remove_image')
        if not self.instance.pk or self.instance._state.adding:
            self.fields.pop('notes')
            # New community events use the same simple fields as the editor.
            # Removed historical configuration is retained on existing events.
            self.instance.event_category = 'general'
            self.instance.target_audience = ''
            self.instance.who_may_participate = ''
            self.instance.capacity = None
            self.instance.application_program = None

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'content_type'):
            return prepare_image(image, max_bytes=settings.EVENT_IMAGE_MAX_BYTES, max_pixels=settings.EVENT_IMAGE_MAX_PIXELS)
        return image

    def clean(self):
        cleaned = super().clean()
        if 'notes' in self.fields and not cleaned.get('notes'):
            cleaned['notes'] = 'Event updated from the event editor.'
        from copy import copy
        from programs.terms import guard_event, EVENT_FIELDS
        proposed = copy(self.instance)
        for name in (*EVENT_FIELDS, *PARTICIPATION_FIELDS, 'application_program'):
            if name in cleaned:
                setattr(proposed, name, cleaned[name])
        old = Event.objects.filter(pk=self.instance.pk).first() if not self.instance._state.adding else None
        guard_event(old, proposed)
        guard_participation(old, proposed)
        if self.instance.status in ('published', 'cancelled'):
            from .participation import require_participation_details
            require_participation_details(proposed, scheduled=True)
        if cleaned.get('remove_image'):
            if self.files.get('image'):
                self.add_error('image', 'Choose replacement or removal, not both.')
            else:
                cleaned['image'] = False
        if cleaned.get('image'):
            old_alt = self.instance.image_alt
            if self.files.get('image') or not old_alt.strip() or old_alt == f'Event image for {self.instance.title}':
                cleaned['image_alt'] = f"Event image for {cleaned.get('title', self.instance.title)}"
            else:
                cleaned['image_alt'] = old_alt
        else:
            cleaned['image_alt'] = ''
        if any(key != 'image' or len(self.files.getlist(key)) != 1 for key in self.files):
            self.add_error(None, 'Upload one event image only.')
        return cleaned


class PublishEventForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class EventActionForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=())
    notes = forms.CharField(max_length=2000, label='Reason', widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='I confirm this event status change.')

    def __init__(self, *args, actions, unpublishing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = actions
        if unpublishing:
            self.fields['action'].widget = forms.HiddenInput()
            self.fields['confirm'].label = 'I confirm this event should be unpublished.'
        self.style_fields()
        self.fields['confirm'].widget.attrs['class'] = 'form-check-input'


class RegistrationForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    control_number = forms.CharField(max_length=100, label='PWD control number')
    full_name = forms.CharField(max_length=200, label='Full name')
    birthdate = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    contact_number = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class AttendanceForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=EventRegistration.Status.choices, label='Registration status')
    notes = forms.CharField(max_length=2000, label='Reason / attendance notes', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class AttendanceMemberChoice(forms.ModelChoiceField):
    def label_from_instance(self, member):
        return f'{member.full_name} ({member.control_number}; {member.status})'


class OpenAttendanceForm(StyledForm, forms.Form):
    submission_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    attendee_name = forms.CharField(max_length=200, label='Attendee name')
    member = AttendanceMemberChoice(queryset=Member.objects.none(), required=False,
                                   label='Existing member', empty_label='No member link')
    status = forms.ChoiceField(choices=EventAttendance.Status.choices)
    notes = forms.CharField(max_length=2000, label='Reason / attendance notes',
                           widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        if user.has_perm('members.view_member'):
            self.fields['member'].queryset = Member.objects.all().order_by('full_name', 'pk')
            self.fields['member'].help_text = 'New attendance requires an active selected Member from the linked Program Application. Existing historical member links are preserved.'
        else:
            self.fields.pop('member')
        self.style_fields()
