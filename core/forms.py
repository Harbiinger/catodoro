from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Sign-up with email + password (no username)."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class EmailAuthenticationForm(AuthenticationForm):
    """Login form that asks for an email instead of a username."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields['username']  # AuthenticationForm keeps the name 'username'
        field.label = 'Email'
        field.widget = forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'})

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()
