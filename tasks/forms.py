from django import forms
from django.utils import timezone

from .models import Task

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
