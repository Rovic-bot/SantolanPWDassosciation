from django.contrib.auth.forms import AuthenticationForm


class StaffAuthenticationForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Unable to sign in. Check your credentials or try again later.',
        'inactive': 'Unable to sign in. Check your credentials or try again later.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
