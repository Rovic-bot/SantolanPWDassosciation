from django import forms
from membership.forms import StyledForm


class QuickReviewForm(forms.Form):
    member_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    review_id = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    document_digest = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)


class ReviewForm(StyledForm, forms.Form):
    member_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    verified = forms.TypedChoiceField(choices=[('yes', 'Verified and current'), ('no', 'Not verified / no longer current')],
                                     coerce=lambda value: value == 'yes')
    expires_on = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
