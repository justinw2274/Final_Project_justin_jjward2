from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Team(models.Model):
    """NBA Team model with advanced statistics for ML predictions"""
    CONFERENCE_CHOICES = [
        ('EAST', 'Eastern Conference'),
        ('WEST', 'Western Conference'),
    ]

    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=3, unique=True)
    conference = models.CharField(max_length=4, choices=CONFERENCE_CHOICES)
    logo_url = models.URLField(blank=True, null=True)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)

    # Dean Oliver's Four Factors (Offense)
    efg_pct = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.500,
        help_text="Effective Field Goal % - (FGM + 0.5*3PM) / FGA"
    )
    tov_pct = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.130,
        help_text="Turnover % - TOV / (FGA + 0.44*FTA + TOV)"
    )
    orb_pct = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.250,
        help_text="Offensive Rebound % - ORB / (ORB + Opp DRB)"
    )
    ft_rate = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.250,
        help_text="Free Throw Rate - FTA / FGA"
    )

    # Four Factors (Defense - opponent stats)
    opp_efg_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.500)
    opp_tov_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.130)
    opp_orb_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.250)
    opp_ft_rate = models.DecimalField(max_digits=5, decimal_places=3, default=0.250)

    # Efficiency Ratings (per 100 possessions)
    offensive_rating = models.DecimalField(
        max_digits=5, decimal_places=1, default=110.0,
        help_text="Points scored per 100 possessions"
    )
    defensive_rating = models.DecimalField(
        max_digits=5, decimal_places=1, default=110.0,
        help_text="Points allowed per 100 possessions"
    )

    # Pace and tempo
    pace = models.DecimalField(
        max_digits=5, decimal_places=1, default=100.0,
        help_text="Possessions per 48 minutes"
    )

    # Elo Rating (start at 1500)
    elo_rating = models.DecimalField(
        max_digits=7, decimal_places=1, default=1500.0,
        help_text="Elo rating for win probability calculations"
    )

    # Recent form (last 10 games)
    last_10_wins = models.IntegerField(default=0)
    last_10_losses = models.IntegerField(default=0)

    # Average stats
    avg_points_scored = models.DecimalField(max_digits=5, decimal_places=1, default=110.0)
    avg_points_allowed = models.DecimalField(max_digits=5, decimal_places=1, default=110.0)

    # Last game date (for rest calculations)
    last_game_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.city} {self.name}"

    @property
    def win_percentage(self):
        total = self.wins + self.losses
        if total == 0:
            return 0.5
        return round(self.wins / total, 3)

    @property
    def record(self):
        return f"{self.wins}-{self.losses}"

    @property
    def net_rating(self):
        """Net rating = Offensive Rating - Defensive Rating"""
        return float(self.offensive_rating) - float(self.defensive_rating)

    @property
    def last_10_record(self):
        return f"{self.last_10_wins}-{self.last_10_losses}"

    @property
    def four_factors_score(self):
        """
        Composite Four Factors score using Dean Oliver's weights.
        Higher is better. Combines offensive and defensive factors.
        """
        # Offensive factors (higher eFG, ORB, FTR is better; lower TOV is better)
        off_score = (
            float(self.efg_pct) * 0.40 +
            (1 - float(self.tov_pct)) * 0.25 +
            float(self.orb_pct) * 0.20 +
            float(self.ft_rate) * 0.15
        )
        # Defensive factors (lower opp stats is better)
        def_score = (
            (1 - float(self.opp_efg_pct)) * 0.40 +
            float(self.opp_tov_pct) * 0.25 +
            (1 - float(self.opp_orb_pct)) * 0.20 +
            (1 - float(self.opp_ft_rate)) * 0.15
        )
        return (off_score + def_score) / 2


class Player(models.Model):
    """NBA Player model"""
    POSITION_CHOICES = [
        ('PG', 'Point Guard'),
        ('SG', 'Shooting Guard'),
        ('SF', 'Small Forward'),
        ('PF', 'Power Forward'),
        ('C', 'Center'),
    ]

    name = models.CharField(max_length=200)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    position = models.CharField(max_length=2, choices=POSITION_CHOICES)
    jersey_number = models.IntegerField(null=True, blank=True)
    avg_points = models.DecimalField(max_digits=4, decimal_places=1, default=0.0)
    avg_rebounds = models.DecimalField(max_digits=4, decimal_places=1, default=0.0)
    avg_assists = models.DecimalField(max_digits=4, decimal_places=1, default=0.0)

    class Meta:
        ordering = ['team', 'name']

    def __str__(self):
        return f"{self.name} ({self.team.abbreviation})"


class Game(models.Model):
    """NBA Game model with prediction data"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('final', 'Final'),
    ]

    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_games')
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Prediction fields
    prediction_home_win_prob = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Predicted probability of home team winning (0-100%)"
    )
    prediction_confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Model confidence in the prediction (0-100%)"
    )
    predicted_spread = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Predicted point spread (positive = home team favored)"
    )

    is_featured = models.BooleanField(default=False, help_text="Feature this game on the homepage")

    class Meta:
        ordering = ['-date', 'time']
        unique_together = ['date', 'home_team', 'away_team']

    def __str__(self):
        return f"{self.away_team.abbreviation} @ {self.home_team.abbreviation} - {self.date}"

    @property
    def winner(self):
        if self.status != 'final' or self.home_score is None or self.away_score is None:
            return None
        return self.home_team if self.home_score > self.away_score else self.away_team

    @property
    def predicted_winner(self):
        if self.prediction_home_win_prob is None:
            return None
        return self.home_team if self.prediction_home_win_prob >= 50 else self.away_team

    @property
    def prediction_correct(self):
        if self.winner is None or self.predicted_winner is None:
            return None
        return self.winner == self.predicted_winner


class UserPick(models.Model):
    """User predictions/votes for games"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='picks')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='user_picks')
    picked_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='user_picks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'game']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} picks {self.picked_team.abbreviation} for {self.game}"

    @property
    def is_correct(self):
        if self.game.winner is None:
            return None
        return self.picked_team == self.game.winner


class UserProfile(models.Model):
    """Extended user profile for tracking stats"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    favorite_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    total_picks = models.IntegerField(default=0)
    correct_picks = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def accuracy(self):
        if self.total_picks == 0:
            return 0.0
        return round((self.correct_picks / self.total_picks) * 100, 1)
