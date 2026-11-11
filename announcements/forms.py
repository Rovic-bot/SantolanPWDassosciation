from django import forms
from membership.forms import StyledForm
from .images import prepare_image
from .models import Announcement


class AnnouncementForm(StyledForm, forms.ModelForm):
    category = forms.ChoiceField(choices=(('general', 'General'), ('programs', 'Programs')),
        help_text='Program Results use the separate Prepare program results action and its approval checks.')
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    image = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept': '.png,.jpg,.jpeg'}),
                            help_text='Optional PNG or JPEG. Publish only images approved for public use.')
    remove_image = forms.BooleanField(required=False, label='Remove the current image')

    class Meta:
        model = Announcement
        fields = ('category', 'source_office', 'linked_program', 'title', 'content', 'image', 'image_alt')
        widgets = {'content': forms.Textarea(attrs={'rows': 12}),
                   'image': forms.ClearableFileInput(attrs={'accept': '.png,.jpg,.jpeg'})}
        labels = {'image_alt': 'Image description', 'source_office': 'Responsible source or office',
                  'linked_program': 'Program to announce'}
        help_texts = {'content': 'Write the complete announcement. Plain text and paragraph breaks are supported.',
                      'image': 'Optional PNG or JPEG. Publish only images approved for public use.',
                      'image_alt': 'Describe the image for people using screen readers. Required when an image is attached.'}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .notices import announcement_programs
        self.fields['linked_program'].queryset = announcement_programs().order_by('name')
        if not user or not user.has_perm('programs.view_program'):
            self.fields['linked_program'].queryset = self.fields['linked_program'].queryset.none()
            self.fields['category'].choices = [('general', 'General')]
        self.fields['linked_program'].help_text = 'Choose an available or upcoming published program. Its current name and overview appear automatically.'
        self.fields['source_office'].required = True
        self.fields['source_office'].help_text = 'Identify the office responsible for the notice, for example the Association, Barangay, or PDAO.'
        self.initial['category'] = self.instance.category
        for name in ('title', 'content'):
            self.fields[name].required = False
        self.initial['version'] = self.instance.version
        self.style_fields()
        self.fields['remove_image'].widget.attrs['class'] = 'form-check-input'
        if not self.instance.image:
            self.fields.pop('remove_image')

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'content_type'):
            return prepare_image(image)
        return image

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('category') == 'programs':
            if not cleaned.get('linked_program'):
                self.add_error('linked_program', 'Choose a current published program.')
            # Store no copy of the program headline or overview that could become inconsistent.
            cleaned['title'] = 'Program announcement'
            cleaned['content'] = 'View the linked program for current information.'
            if cleaned.get('image') and not cleaned.get('remove_image'):
                self.add_error('image', 'Program previews use the linked program. Remove the General announcement image first.')
            cleaned['image_alt'] = ''
        elif cleaned.get('category') == 'general':
            cleaned['linked_program'] = None
            for name in ('title', 'content'):
                if not cleaned.get(name):
                    self.add_error(name, 'This field is required for General announcements.')
        if cleaned.get('remove_image'):
            if self.files.get('image'):
                self.add_error('image', 'Choose either a replacement image or removal, not both.')
            else:
                cleaned['image'] = False
                cleaned['image_alt'] = ''
        if cleaned.get('image') and not cleaned.get('image_alt'):
            self.add_error('image_alt', 'Describe the attached image.')
        if any(key != 'image' or len(self.files.getlist(key)) != 1 for key in self.files):
            self.add_error(None, 'Upload one announcement image only.')
        return cleaned


class AnnouncementComposerForm(StyledForm, forms.ModelForm):
    """Three-field editor for Association notices; retained program notices use their original form."""
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    image = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept': '.png,.jpg,.jpeg'}))
    remove_image = forms.BooleanField(required=False, label='Remove the current image')

    class Meta:
        model = Announcement
        fields = ('title', 'content', 'image')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Community meeting this Saturday'}),
            'content': forms.Textarea(attrs={'rows': 7,
                'placeholder': 'Share what is happening, when and where, and what members need to do.'}),
        }
        help_texts = {'content': 'Include all important information here, including any details shown in the image.'}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['version'] = self.instance.version
        self.style_fields()
        if not self.instance.image:
            self.fields.pop('remove_image')
        else:
            self.fields['remove_image'].widget.attrs['class'] = 'form-check-input'

    clean_image = AnnouncementForm.clean_image

    def clean(self):
        cleaned = super().clean()
        if self.instance.linked_program_id or self.instance.program_id:
            self.add_error(None, 'Use the program announcement review to update this record.')
        if any(key != 'image' or len(self.files.getlist(key)) != 1 for key in self.files):
            self.add_error(None, 'Upload one announcement image only.')
        if cleaned.get('remove_image'):
            if self.files.get('image'):
                self.add_error('image', 'Choose either a replacement image or removal, not both.')
            else:
                cleaned['image'] = False
        # The composer publishes on behalf of the Association. Preserve the source
        # and image description of existing notices when their image is unchanged.
        self.instance.source_office = self.instance.source_office or 'Barangay Santolan PWD Association'
        if not cleaned.get('image'):
            self.instance.image_alt = ''
        elif self.files.get('image') or not self.instance.image_alt:
            self.instance.image_alt = f"Image accompanying {cleaned.get('title', 'this announcement')}"[:250]
        return cleaned


class PublicationForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=())
    confirm = forms.BooleanField(label='I confirm this change to the announcement.')

    def __init__(self, *args, actions, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = actions
        self.style_fields()
        self.fields['confirm'].widget.attrs['class'] = 'form-check-input'


class ResultDraftForm(StyledForm, forms.Form):
    program = forms.ModelChoiceField(queryset=None, label='Program')
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, program=None, **kwargs):
        from programs.models import Program
        super().__init__(*args, **kwargs)
        self.fields['program'].queryset = Program.objects.exclude(status='draft')
        if program:
            self.fields['program'].initial = program
            self.fields['program'].disabled = True
        self.style_fields()


class GenerateResultsForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    expected = forms.CharField(max_length=64, widget=forms.HiddenInput)
    selection_reason = forms.CharField(max_length=2000, label='Reason for selecting these members',
        help_text='This explanation will appear with the public results. Describe the shared program criteria; leave out names, private medical details and individual scores.',
        error_messages={'required': 'Explain why these members were selected before publishing the results.'},
        widget=forms.Textarea(attrs={'rows': 3, 'form': 'generate-results-form',
            'data-selection-reason': '', 'aria-describedby': 'selection-reason-help',
            'placeholder': 'Explain how the selected members meet this program’s requirements and why this assistance addresses their needs.'}))
