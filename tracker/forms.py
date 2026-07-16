from django import forms
from django.contrib.auth.models import User
from .models import Spool, FilamentProduct

_input_cls = 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
_select_cls = _input_cls


class SpoolForm(forms.ModelForm):
    full_weight_g = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': _input_cls, 'placeholder': 'default: 1000'}),
    )

    def clean_full_weight_g(self):
        value = self.cleaned_data.get('full_weight_g')
        return value if value is not None else 1000

    class Meta:
        model = Spool
        fields = [
            'sku', 'brand', 'material', 'color_name', 'color_hex',
            'diameter_mm', 'full_weight_g', 'remaining_g',
            'price_paid', 'purchase_date', 'notes',
        ]
        widgets = {
            'sku': forms.TextInput(attrs={
                'class': _input_cls,
                'placeholder': 'e.g. 02151201A',
                'hx-get': '/inventory/sku-lookup/',
                'hx-trigger': 'change, keyup[key=="Enter"]',
                'hx-target': '#sku-status',
                'hx-swap': 'innerHTML',
            }),
            'brand': forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'e.g. Bambu Lab'}),
            'material': forms.TextInput(attrs={
                'class': _input_cls,
                'placeholder': 'e.g. PLA, PETG, ABS, TPU',
                'list': 'material-suggestions',
            }),
            'color_name': forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'e.g. Light Gold'}),
            'color_hex': forms.TextInput(attrs={
                'type': 'color',
                'class': 'h-10 w-16 rounded-md border border-gray-300 cursor-pointer p-0.5',
            }),
            'diameter_mm': forms.NumberInput(attrs={'class': _input_cls, 'step': '0.01', 'placeholder': '1.75'}),
            'remaining_g': forms.NumberInput(attrs={'class': _input_cls, 'placeholder': '1000', 'step': '0.1'}),
            'price_paid': forms.NumberInput(attrs={'class': _input_cls, 'placeholder': '0.00', 'step': '0.01'}),
            'purchase_date': forms.DateInput(attrs={'class': _input_cls, 'type': 'text', 'data-date-picker': ''}),
            'notes': forms.Textarea(attrs={'class': _input_cls, 'rows': 3, 'placeholder': 'Optional notes'}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': _input_cls}),
            'email': forms.EmailInput(attrs={'class': _input_cls}),
        }


class FilamentProductForm(forms.ModelForm):
    class Meta:
        model = FilamentProduct
        fields = ['sku', 'brand', 'material', 'color_name', 'color_hex', 'full_weight_g', 'diameter_mm']
        widgets = {
            'sku': forms.TextInput(attrs={'class': _input_cls}),
            'brand': forms.TextInput(attrs={'class': _input_cls}),
            'material': forms.TextInput(attrs={'class': _input_cls, 'list': 'material-suggestions'}),
            'color_name': forms.TextInput(attrs={'class': _input_cls}),
            'color_hex': forms.TextInput(attrs={
                'type': 'color',
                'class': 'h-10 w-16 rounded-md border border-gray-300 cursor-pointer p-0.5',
            }),
            'full_weight_g': forms.NumberInput(attrs={'class': _input_cls}),
            'diameter_mm': forms.NumberInput(attrs={'class': _input_cls, 'step': '0.01'}),
        }
