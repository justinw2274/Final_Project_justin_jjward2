from django import forms
from .models import UserPick, Team


class UserPickForm(forms.Form):
    """Form for users to make game predictions"""
    picked_team = forms.ModelChoiceField(
        queryset=Team.objects.none(),
        widget=forms.RadioSelect,
        label="Who do you think will win?"
    )

    def __init__(self, game, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['picked_team'].queryset = Team.objects.filter(
            pk__in=[game.home_team.pk, game.away_team.pk]
        )


class ExportForm(forms.Form):
    """Form for data export options"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]
    DATE_RANGE_CHOICES = [
        ('week', 'This Week'),
        ('month', 'This Month'),
        ('season', 'Full Season'),
    ]

    format = forms.ChoiceField(choices=FORMAT_CHOICES, initial='csv')
    date_range = forms.ChoiceField(choices=DATE_RANGE_CHOICES, initial='week')
    include_predictions = forms.BooleanField(required=False, initial=True)
    include_user_picks = forms.BooleanField(required=False, initial=False)
