from django import forms


class LocationSearchForm(forms.Form):
    query = forms.CharField(
        min_length=2,
        max_length=120,
        label="Region or local authority",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "placeholder": "e.g. Edinburgh or Bristol",
            }
        ),
    )
