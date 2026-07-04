from django import forms

from .models import Cat

_INPUT = (
    'w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm '
    'text-stone-800 focus:border-pink-500 focus:outline-none focus:ring-2 '
    'focus:ring-pink-200'
)


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
