from django import forms


class LocationSearchForm(forms.Form):
    query = forms.CharField(
        max_length=120,
        label="Town, city, or postcode",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "postal-code",
                "placeholder": "e.g. Bristol or SW1A 1AA",
            }
        ),
    )
