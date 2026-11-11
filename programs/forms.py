from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, When, Q
from documents.validators import validate_document
from events.forms import RegistrationForm, EventActionForm
from membership.forms import StyledForm
from members.models import DisabilityType
from members.disability_catalog import ASSOCIATION_LABELS
from .models import Program, ProgramRequirement, ProgramApplication
from announcements.images import prepare_image
from documents.services import reusable_documents
from .pictures import ProgramPictureForm


class ProgramDisabilityChoiceField(forms.ModelMultipleChoiceField):
    # Display the Association labels while keeping existing classification IDs.
    labels = ASSOCIATION_LABELS

    def label_from_instance(self, obj):
        return self.labels.get(obj.name, obj.name)


class ProgramForm(StyledForm, forms.ModelForm):
    assistance_type = forms.ChoiceField(choices=[
        ('Food & Nutrition', 'Food & Nutrition'),
        ('Healthcare & Medical Aid', 'Healthcare & Medical Aid'),
        ('Assistive Devices', 'Assistive Devices'),
    ])
    def _save_m2m(self):
        from .terms import terms_lock, guard_program_form
        with terms_lock():
            guard_program_form(self)
            return super()._save_m2m()

    def save(self, commit=True):
        from .terms import terms_lock, guard_program_form
        with terms_lock():
            guard_program_form(self)
            return super().save(commit=commit)

    def clean(self):
        values = super().clean()
        self.instance.ewaf_applicable = True
        selected = values.get('eligible_disability_types')
        retained = self.instance.eligible_disability_types.values_list('pk', flat=True) if not self.instance._state.adding else []
        if selected is not None and selected.filter(is_active=False).exclude(pk__in=retained).exists():
            self.add_error('eligible_disability_types', 'A selected disability type is inactive. Ask an administrator to review the choices.')
        if 'eligible_disability_types' in values:
            values['eligible_disability_types'] = DisabilityType.objects.filter(pk__in=[
                *values['eligible_disability_types'].values_list('pk', flat=True),
                *self.legacy_disability_types.values_list('pk', flat=True)])
            if self.terms_protected and self.instance.allows_all_disability_types:
                # The historical empty relation means all types. Keep signed
                # sources intact while the required, locked field displays all.
                values['eligible_disability_types'] = DisabilityType.objects.none()
        from .terms import guard_program_form
        guard_program_form(self, validate_schedule=True)
        return values

    eligible_disability_types = ProgramDisabilityChoiceField(
        queryset=DisabilityType.objects.none(), required=True, label='Applicable disability types',
        widget=forms.CheckboxSelectMultiple,
        help_text='Select at least one disability type, or choose Select all.')
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(max_length=2000, label='Reason for this change', widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = Program
        # Budget is historical data only: exclude it so omitted or forged input
        # cannot overwrite retained values. The Association does not manage it.
        fields = ('name', 'description', 'benefit', 'assistance_type', 'registration_opens_at', 'registration_closes_at',
                  'starts_at', 'ends_at', 'slots', 'requirements', 'eligible_disability_types',
                  'selection_method', 'photo_instructions', 'resubmission_closes_at')
        widgets = {**{name: forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})
                      for name in ('starts_at', 'ends_at', 'registration_opens_at', 'registration_closes_at')},
                   'description': forms.Textarea(attrs={'rows': 5}), 'requirements': forms.Textarea(attrs={'rows': 4})}
        labels = {'name': 'Title', 'slots': 'Beneficiary slots', 'amount': 'Amount per beneficiary (PHP)',
                  'requirements': 'Program requirements and instructions', 'benefit': 'Benefit description'}
        help_texts = {'assistance_type': 'Use the association’s chosen assistance type; no categories are preselected.',
                      'slots': 'Required maximum number of beneficiaries. Applications may exceed this count for later review.',
                      'requirements': 'Public instructions. Add uploads and questions in the Requirements section below.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from members.disability_catalog import current_types, retained_types
        retained = self.instance.eligible_disability_types.values_list('pk', flat=True) if not self.instance._state.adding else []
        self.legacy_disability_types = retained_types(retained)
        disability_field = self.fields['eligible_disability_types']
        disability_field.queryset = current_types().filter(Q(is_active=True) | Q(pk__in=retained)).order_by(Case(
            *[When(name=name, then=index) for index, name in enumerate(disability_field.labels)],
            output_field=IntegerField()))
        self.initial['eligible_disability_types'] = list(current_types().filter(pk__in=retained).values_list('pk', flat=True))
        if not self.instance._state.adding and self.instance.assistance_type and self.instance.assistance_type not in dict(self.fields['assistance_type'].choices):
            # A retained historical category is never silently converted on edit.
            self.fields['assistance_type'].choices = [
                (self.instance.assistance_type, f'{self.instance.assistance_type} (retained)'),
                *self.fields['assistance_type'].choices,
            ]
        self.initial['version'] = self.instance.version
        if self.instance._state.adding:
            self.fields.pop('notes')
        for name, label in (('starts_at', 'Program starts'), ('ends_at', 'Program ends'),
                            ('registration_opens_at', 'Registration opens'), ('registration_closes_at', 'Registration closes')):
            self.fields[name].help_text = ''
            self.fields[name].label = label
        self.style_fields()
        self.fields['selection_method'].help_text = 'Explain how eligible applicants will be selected and how available slots are applied. Use the Association’s approved method; saving this description still requires separate policy authorization.'
        self.fields['photo_instructions'].help_text = 'State the approved calendar-photo recency, legibility and assistance arrangements. A current photo of the Member holding a calendar and manual Admin review are mandatory.'
        self.fields['resubmission_closes_at'].widget = forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'})
        self.fields['resubmission_closes_at'].help_text = 'Optional approved correction deadline in Philippine time. Blank permits Help Desk corrections while the application remains open for processing.'
        self.fields['resubmission_closes_at'].label = 'Correction deadline (optional)'
        self.fields['eligible_disability_types'].widget.attrs['class'] = 'disability-choices'
        for name in ('assistance_type', 'slots', 'selection_method', 'photo_instructions', 'resubmission_closes_at'):
            self.fields[name].help_text = ''
        self.fields['description'].widget.attrs['rows'] = 3
        self.fields['requirements'].widget.attrs['rows'] = 2
        self.fields['requirements'].label = 'Instructions (optional)'
        self.fields['requirements'].help_text = ''
        self.fields['photo_instructions'].label = 'Photo instructions (optional)'
        self.fields['selection_method'].label = 'Beneficiary selection instructions (optional for publication)'
        self.fields['selection_method'].widget.attrs['rows'] = 2
        self.fields['photo_instructions'].widget.attrs['rows'] = 2
        from .application_workflow import enabled
        if enabled():
            self.fields['benefit'].label = 'Purpose and intended benefit'
            self.fields['benefit'].widget = forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
            self.fields['benefit'].help_text = 'Explain what the program aims to address and provide.'
            self.fields['selection_method'].label = 'Beneficiary selection method'
            self.fields['photo_instructions'].label = 'Identity-evidence instructions'
            for name in ('slots', 'selection_method', 'photo_instructions'):
                self.fields[name].required = True
        else:
            self.fields.pop('benefit')
        self.is_incomplete_draft = self.instance.status == 'draft' and not self.instance.published_at and not self.instance.policy_authorized_at
        if self.is_incomplete_draft:
            for name in self.Meta.fields:
                if name in self.fields:
                    self.fields[name].required = False
            if 'notes' in self.fields:
                self.fields['notes'].required = False
            self.fields['assistance_type'].choices = [('', 'Choose assistance type'), *self.fields['assistance_type'].choices]
        else:
            for name in ('name', 'assistance_type', 'registration_opens_at', 'registration_closes_at'):
                self.fields[name].required = True
        from .terms import is_protected
        self.terms_protected = bool(is_protected(self.instance) or self.instance.policy_authorized_at)
        self.fields['slots'].required = True
        self.fields['slots'].help_text = 'Required. Enter the maximum number of beneficiaries.'
        self.fields['slots'].widget.attrs['min'] = 1
        self.fields['eligible_disability_types'].required = not self.legacy_disability_types.exists()
        if not self.instance._state.adding and self.instance.allows_all_disability_types:
            self.initial['eligible_disability_types'] = list(disability_field.queryset.filter(is_active=True).values_list('pk', flat=True))

    @property
    def sections(self):
        groups = [
            ('Basic Program Information', ('name', 'assistance_type', 'description', 'benefit')),
            ('Registration and Program Schedule', ('registration_opens_at', 'registration_closes_at', 'starts_at', 'ends_at', 'resubmission_closes_at')),
            ('Beneficiary Slots', ('slots', 'selection_method')),
            ('Applicable Disability Types', ('eligible_disability_types',)),
            ('Additional Requirements', ('requirements', 'photo_instructions')),
        ]
        return [(heading, [self[name] for name in names if name in self.fields]) for heading, names in groups]


class ProgramSetupForm(ProgramForm, ProgramPictureForm):
    """The simplified setup never clears or rewrites retained policy text."""
    omitted_fields = ('requirements', 'selection_method', 'photo_instructions')

    def clean(self):
        values = super().clean()
        if values.get('picture') and values.get('remove_picture'):
            self.add_error('picture', 'Choose a new picture or remove the current one, not both.')
        return values

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.omitted_fields:
            self.fields.pop(name)
        if self.terms_protected:
            for name in ('eligible_disability_types',):
                self.fields[name].disabled = True
        picture = getattr(self.instance, 'picture_asset', None) if not self.instance._state.adding else None
        self.initial['picture_version'] = picture.version if picture else 0
        self.fields['picture'].help_text = (
            f'Optional JPG or PNG, up to {settings.ANNOUNCEMENT_IMAGE_MAX_BYTES // 1048576} MB. '
            'Shown in Program Details. Without a picture, the program title initials are used.')
        self.fields['remove_picture'].widget.attrs['class'] = 'form-check-input'


class PublishProgramForm(forms.Form):
    """The Publish button is the explicit action; no second confirmation."""
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class PublicationForm(EventActionForm):
    confirm = forms.BooleanField(label='I confirm this program action and its recorded approval.')

    def __init__(self, *args, archive_action='', **kwargs):
        super().__init__(*args, **kwargs)
        if archive_action:
            self.fields['action'].widget = forms.HiddenInput()
            self.fields['confirm'].label = (
                'I confirm this program should be unpublished and returned to draft.' if archive_action == 'unpublish'
                else 'I confirm this program should be archived.')


class RequirementForm(StyledForm, forms.ModelForm):
    def save(self, commit=True):
        from .terms import terms_lock, guard_requirement_form
        with terms_lock():
            guard_requirement_form(self)
            return super().save(commit=commit)

    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(max_length=2000, label='Reason', widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = ProgramRequirement
        fields = ('label', 'kind', 'instructions', 'is_required', 'is_active', 'position', 'reusable_document_type')
        widgets = {'instructions': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'is_active': 'Deactivate an obsolete requirement. Submitted application snapshots are retained.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        for name in ('is_required', 'is_active'):
            self.fields[name].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        values = super().clean()
        from .terms import guard_requirement_form
        guard_requirement_form(self)
        if values.get('reusable_document_type') and values.get('kind') != 'document':
            self.add_error('reusable_document_type', 'Only document requirements can reuse an internal document.')
        return values


class NewRequirementForm(StyledForm, forms.Form):
    label = forms.CharField(max_length=150, label='Requirement name')
    kind = forms.ChoiceField(choices=ProgramRequirement.Kind.choices)
    instructions = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))
    is_required = forms.BooleanField(required=False, initial=True, label='Required')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['is_required'].widget.attrs['class'] = 'form-check-input'


NewRequirementFormSet = forms.formset_factory(NewRequirementForm, extra=0, max_num=50,
                                             validate_max=True, absolute_max=50)


def snapshot(program):
    return list(program.configured_requirements.filter(is_active=True).values(
        'id', 'label', 'kind', 'instructions', 'is_required', 'position', 'reusable_document_type_id'))


class MembershipCheckForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    control_number = forms.CharField(max_length=100, label='PWD control number')
    full_name = forms.CharField(max_length=200, label='Full name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class ApplicationForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    calendar_photo = forms.FileField(label='Current photo of the Member holding a calendar',
        help_text='Required private identity evidence. An authorized Admin reviews it manually. Contact the Help Desk if you need assistance.',
        widget=forms.FileInput(attrs={'accept': '.png,.jpg,.jpeg'}))

    def __init__(self, *args, program, member=None, require_calendar_photo=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_calendar_photo = require_calendar_photo
        if not require_calendar_photo:
            self.fields.pop('calendar_photo')
        self.snapshot = snapshot(program)
        self.reused = reusable_documents(member, self.snapshot)
        self.initial['version'] = program.version
        for item in self.snapshot:
            options = {'label': item['label'], 'required': item['is_required'], 'help_text': item['instructions']}
            if item['kind'] == 'document':
                options['required'] = item['is_required'] and item['id'] not in self.reused
                field = forms.FileField(**options, validators=[validate_document], widget=forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg'}))
            elif item['kind'] == 'acknowledgement':
                field = forms.BooleanField(**options)
            else:
                field = forms.CharField(**options, max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))
            self.fields[f'requirement_{item["id"]}'] = field
        self.style_fields()
        for field in self.fields.values():
            if isinstance(field, forms.BooleanField):
                field.widget.attrs['class'] = 'form-check-input'

    def clean(self):
        cleaned = super().clean()
        expected = {name for name, field in self.fields.items() if isinstance(field, forms.FileField)}
        if any(key not in expected or len(self.files.getlist(key)) != 1 for key in self.files):
            raise ValidationError('Upload only one file per listed document requirement.')
        if sum(upload.size for uploads in self.files.lists() for upload in uploads[1]) > settings.MEMBERSHIP_TOTAL_MAX_BYTES:
            raise ValidationError('The combined uploads exceed the upload limit.')
        return cleaned

    def clean_calendar_photo(self):
        return prepare_image(self.cleaned_data['calendar_photo'], max_bytes=settings.MEMBERSHIP_FILE_MAX_BYTES)


class ApplicationStatusForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=[('CLOSED', 'Close application')])
    notes = forms.CharField(max_length=2000, label='Reason / review notes', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class PhotoReviewForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    photo_id = forms.UUIDField(widget=forms.HiddenInput)
    outcome = forms.ChoiceField(choices=[('VERIFIED', 'Verified'), ('NEEDS_RESUBMISSION', 'Needs Resubmission'), ('REJECTED', 'Rejected / Verification Failed')])
    category = forms.CharField(max_length=120, required=False, help_text='Required for rejection/resubmission, using the association’s reason category.')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='I manually reviewed the current photo and identity evidence against the approved program instructions.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['confirm'].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        values = super().clean()
        if values.get('outcome') != 'VERIFIED' and not values.get('category'):
            self.add_error('category', 'Record a reason category for this outcome.')
        return values


class CorrectionForm(ApplicationForm):
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}), label='Help Desk correction reason')

    def __init__(self, *args, application, **kwargs):
        self.application = application
        from .workflow import calendar_photo_required
        super().__init__(*args, program=application.program, member=application.member,
                         require_calendar_photo=calendar_photo_required(application), **kwargs)
        self.initial['version'] = application.version
        if 'calendar_photo' in self.fields:
            self.fields['calendar_photo'].required = not bool(application.current_photo_id)
        for item in self.snapshot:
            key = f'requirement_{item["id"]}'
            if item['kind'] == 'document' and application.documents.filter(requirement_id=item['id']).exists():
                self.fields[key].required = False
            elif item['kind'] != 'document':
                self.initial[key] = application.answers.get(str(item['id']), '')
        self.style_fields()

    def clean_calendar_photo(self):
        photo = self.cleaned_data.get('calendar_photo')
        return prepare_image(photo, max_bytes=settings.MEMBERSHIP_FILE_MAX_BYTES) if photo else None
