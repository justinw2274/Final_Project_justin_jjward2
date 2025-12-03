from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from core.models import Team


class CustomUserCreationForm(UserCreationForm):
    """Extended user registration form"""
    email = forms.EmailField(required=True)
    favorite_team = forms.ModelChoiceField(
        queryset=Team.objects.all(),
        required=False,
        label="Favorite Team (optional)"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with Bootstrap styling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
