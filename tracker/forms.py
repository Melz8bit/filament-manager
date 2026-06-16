from django import forms
from .models import Spool

_input_cls = 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
_select_cls = _input_cls


class SpoolForm(forms.ModelForm):
    class Meta:
        model = Spool
        fields = [
            'brand', 'material', 'color_name', 'color_hex',
            'full_weight_g', 'remaining_g', 'price_paid', 'purchase_date', 'notes',
        ]
        widgets = {
            'brand': forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'e.g. Bambu Lab'}),
            'material': forms.TextInput(attrs={
                'class': _input_cls,
                'placeholder': 'e.g. PLA, PETG, ABS, TPU',
                'list': 'material-suggestions',
            }),
            'color_name': forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'e.g. Bambu Green'}),
            'color_hex': forms.TextInput(attrs={
                'type': 'color',
                'class': 'h-10 w-16 rounded-md border border-gray-300 cursor-pointer p-0.5',
            }),
            'full_weight_g': forms.NumberInput(attrs={'class': _input_cls, 'placeholder': '1000'}),
            'remaining_g': forms.NumberInput(attrs={'class': _input_cls, 'placeholder': '1000', 'step': '0.1'}),
            'price_paid': forms.NumberInput(attrs={'class': _input_cls, 'placeholder': '0.00', 'step': '0.01'}),
            'purchase_date': forms.DateInput(attrs={'class': _input_cls, 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': _input_cls, 'rows': 3, 'placeholder': 'Optional notes'}),
        }
