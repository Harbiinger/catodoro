from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils import timezone

from .models import Cat, Task

User = get_user_model()

_INPUT = (
    'w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm '
    'text-stone-800 focus:border-pink-500 focus:outline-none focus:ring-2 '
    'focus:ring-pink-200'
)


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'deadline', 'estimated_pomodoros', 'difficulty']
        widgets = {
            'title': forms.TextInput(
                attrs={'class': _INPUT, 'placeholder': 'Finish the quarterly report'}
            ),
            'deadline': forms.DateTimeInput(
                attrs={'class': _INPUT, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'estimated_pomodoros': forms.NumberInput(attrs={'class': _INPUT, 'min': 1}),
            'difficulty': forms.Select(attrs={'class': _INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        deadline = self.fields['deadline']
        deadline.input_formats = ['%Y-%m-%dT%H:%M']
        # Start empty; just prevent picking a time in the past.
        deadline.widget.attrs['min'] = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if deadline < timezone.now():
            raise forms.ValidationError('Deadline must be in the future.')
        return deadline


class CatSetupForm(forms.ModelForm):
    """Onboarding: pick the cat's name and colour.

    The colour swatches are rendered manually in the template as radio inputs
    named ``color``; this form still validates the submitted value against the
    model's choices.
    """

    class Meta:
        model = Cat
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': _INPUT, 'placeholder': 'Miso', 'maxlength': 40,
                'autofocus': True,
            }),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('Please give your cat a name.')
        return name


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
