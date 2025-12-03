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

    # Streak tracking
    current_streak = models.IntegerField(default=0, help_text="Positive=wins, negative=losses")
    home_streak = models.IntegerField(default=0)
    away_streak = models.IntegerField(default=0)

    # Situational records
    record_vs_above_500_wins = models.IntegerField(default=0)
    record_vs_above_500_losses = models.IntegerField(default=0)
    record_vs_below_500_wins = models.IntegerField(default=0)
    record_vs_below_500_losses = models.IntegerField(default=0)

    # Schedule difficulty
    strength_of_schedule = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.500,
        help_text="Average opponent win percentage"
    )
    avg_opponent_elo = models.DecimalField(
        max_digits=7, decimal_places=1, default=1500.0
    )

    # Rolling stats (last 10 games for recent form)
    rolling_fg_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.450)
    rolling_3p_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.350)
    rolling_ft_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.780)
    rolling_orb = models.DecimalField(max_digits=5, decimal_places=1, default=10.0)
    rolling_drb = models.DecimalField(max_digits=5, decimal_places=1, default=34.0)
    rolling_ast = models.DecimalField(max_digits=5, decimal_places=1, default=24.0)
    rolling_tov = models.DecimalField(max_digits=5, decimal_places=1, default=14.0)
    rolling_stl = models.DecimalField(max_digits=5, decimal_places=1, default=7.5)
    rolling_blk = models.DecimalField(max_digits=5, decimal_places=1, default=5.0)

    # Performance trend (positive = improving)
    points_trend = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.0,
        help_text="Scoring trend over last 10 games"
    )
    defense_trend = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.0,
        help_text="Defensive trend (negative = improving)"
    )

    # Back-to-back tracking
    games_last_7_days = models.IntegerField(default=0)
    back_to_backs_played = models.IntegerField(default=0)

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
    predicted_home_score = models.IntegerField(
        null=True, blank=True,
        help_text="Predicted score for home team"
    )
    predicted_away_score = models.IntegerField(
        null=True, blank=True,
        help_text="Predicted score for away team"
    )

    # Vegas betting lines (for ATS/O/U tracking)
    vegas_spread = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Vegas spread (positive = home team favored)"
    )
    vegas_total = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Vegas over/under total"
    )
    vegas_home_ml = models.IntegerField(
        null=True, blank=True,
        help_text="Vegas home team moneyline"
    )
    vegas_away_ml = models.IntegerField(
        null=True, blank=True,
        help_text="Vegas away team moneyline"
    )

    is_featured = models.BooleanField(default=False, help_text="Feature this game on the homepage")

    # Schedule context (calculated BEFORE game for prediction - no data leakage)
    home_rest_days = models.IntegerField(default=2, help_text="Days since home team's last game")
    away_rest_days = models.IntegerField(default=2, help_text="Days since away team's last game")
    home_b2b = models.BooleanField(default=False, help_text="Home team on back-to-back")
    away_b2b = models.BooleanField(default=False, help_text="Away team on back-to-back")
    home_3in4 = models.BooleanField(default=False, help_text="Home team 3 games in 4 nights")
    away_3in4 = models.BooleanField(default=False, help_text="Away team 3 games in 4 nights")

    # Pre-game team snapshots (for accurate historical predictions without leakage)
    home_elo_pre = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    away_elo_pre = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    home_streak_pre = models.IntegerField(default=0, help_text="Home team streak before game")
    away_streak_pre = models.IntegerField(default=0, help_text="Away team streak before game")

    # H2H context (season record before this game)
    h2h_home_wins = models.IntegerField(default=0)
    h2h_away_wins = models.IntegerField(default=0)

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

    @property
    def actual_spread(self):
        """Actual spread (positive = home team won by X)"""
        if self.status != 'final' or self.home_score is None:
            return None
        return self.home_score - self.away_score

    @property
    def actual_total(self):
        """Actual game total"""
        if self.status != 'final' or self.home_score is None:
            return None
        return self.home_score + self.away_score

    @property
    def model_ats_result(self):
        """
        Model's ATS result using Vegas lines.

        Logic: Use our prediction to decide which side of Vegas line to bet,
        then check if that bet would have won.

        Example:
        - Our prediction: CLE -11 (we think CLE wins by 11)
        - Vegas line: CLE -4.5
        - Since we predict bigger margin than Vegas, bet CLE to cover
        - If CLE wins by 6: Vegas line was -4.5, actual margin 6 > 4.5, CLE covered → WIN

        Returns 'W' (win), 'L' (loss), 'P' (push), or None
        """
        if self.actual_spread is None or self.predicted_spread is None:
            return None
        if self.vegas_spread is None:
            return None  # Need Vegas line to evaluate bet

        predicted = float(self.predicted_spread)
        vegas = float(self.vegas_spread)
        actual = self.actual_spread

        # Determine which side to bet based on our prediction vs Vegas
        # If we predict home wins by MORE than Vegas, bet home to cover
        # If we predict home wins by LESS than Vegas, bet away to cover
        bet_home = predicted > vegas

        # Check if our bet won against the Vegas line
        home_covered = actual > vegas  # Did home beat the Vegas spread?

        # Handle push (actual equals Vegas line)
        if abs(actual - vegas) < 0.5:
            return 'P'

        # Did our bet win?
        if bet_home and home_covered:
            return 'W'  # We bet home, home covered
        elif not bet_home and not home_covered:
            return 'W'  # We bet away, away covered (home didn't cover)
        else:
            return 'L'  # Our bet lost

    @property
    def model_ou_result(self):
        """
        Model's O/U result using Vegas lines.

        Logic: Use our predicted total to decide over/under on Vegas total,
        then check if that bet would have won.

        Example:
        - Our predicted total: 227
        - Vegas total: 220
        - Since we predict higher, bet OVER
        - If actual total is 225: 225 > 220, over hit → WIN

        Returns 'O' (over), 'U' (under), 'P' (push), or None
        """
        if self.actual_total is None or self.predicted_home_score is None:
            return None
        if self.vegas_total is None:
            return None  # Need Vegas total to evaluate bet

        predicted_total = self.predicted_home_score + self.predicted_away_score
        vegas_total = float(self.vegas_total)
        actual = self.actual_total

        # Determine over/under based on our prediction vs Vegas
        bet_over = predicted_total > vegas_total

        # Check actual result vs Vegas line
        went_over = actual > vegas_total

        # Handle push
        if abs(actual - vegas_total) < 0.5:
            return 'P'

        # Did our bet win?
        if bet_over and went_over:
            return 'O'  # We bet over, it went over → WIN (return 'O' to indicate over hit)
        elif not bet_over and not went_over:
            return 'U'  # We bet under, it went under → WIN (return 'U' to indicate under hit)
        elif bet_over and not went_over:
            return 'L'  # We bet over, it went under → LOSS
        else:
            return 'L'  # We bet under, it went over → LOSS

    @property
    def vegas_ats_result(self):
        """
        ATS result vs Vegas line (if available)
        Returns 'W', 'L', 'P', or None
        """
        if self.actual_spread is None or self.vegas_spread is None:
            return None

        vegas = float(self.vegas_spread)
        actual = self.actual_spread

        diff = actual - vegas

        if abs(diff) < 0.5:
            return 'P'
        elif diff > 0:
            return 'W'  # Home covered vs Vegas
        else:
            return 'L'

    @property
    def vegas_ou_result(self):
        """
        O/U result vs Vegas total (if available)
        Returns 'O', 'U', 'P', or None
        """
        if self.actual_total is None or self.vegas_total is None:
            return None

        vegas = float(self.vegas_total)
        actual = self.actual_total

        diff = actual - vegas

        if abs(diff) < 0.5:
            return 'P'
        elif diff > 0:
            return 'O'
        else:
            return 'U'


class HeadToHead(models.Model):
    """Track head-to-head records between teams for a season"""
    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='h2h_as_team1')
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='h2h_as_team2')
    season = models.CharField(max_length=10, default='2025-26')  # e.g., "2025-26"
    team1_wins = models.IntegerField(default=0)
    team2_wins = models.IntegerField(default=0)
    team1_points = models.IntegerField(default=0)  # Total points scored
    team2_points = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)

    class Meta:
        unique_together = ['team1', 'team2', 'season']

    def __str__(self):
        return f"{self.team1.abbreviation} vs {self.team2.abbreviation} ({self.season})"

    @property
    def avg_point_diff(self):
        """Average point differential (positive = team1 favored)"""
        if self.games_played == 0:
            return 0
        return (self.team1_points - self.team2_points) / self.games_played


class UserPick(models.Model):
    """User predictions/votes for games"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='picks')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='user_picks')
    picked_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='user_picks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    evaluated = models.BooleanField(default=False)  # Track if pick has been counted in user stats

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


class HistoricalGame(models.Model):
    """
    Historical NBA game data for ML model training.
    Stores game results and pre-game features calculated from rolling history.
    """
    # Game identification
    api_game_id = models.IntegerField(unique=True, help_text="Game ID from balldontlie API")
    date = models.DateField()
    season = models.IntegerField(help_text="Season year (e.g., 2024 for 2024-25 season)")

    # Teams (stored as abbreviations to handle historical teams)
    home_team_abbr = models.CharField(max_length=5)
    away_team_abbr = models.CharField(max_length=5)

    # Actual scores
    home_score = models.IntegerField()
    away_score = models.IntegerField()

    # Pre-game features (calculated from rolling history)
    # Team win percentages going into game
    home_win_pct = models.DecimalField(max_digits=5, decimal_places=3, null=True)
    away_win_pct = models.DecimalField(max_digits=5, decimal_places=3, null=True)

    # Rolling averages (last 10 games before this game)
    home_ppg_l10 = models.DecimalField(max_digits=5, decimal_places=1, null=True, help_text="Home team PPG last 10")
    away_ppg_l10 = models.DecimalField(max_digits=5, decimal_places=1, null=True, help_text="Away team PPG last 10")
    home_papg_l10 = models.DecimalField(max_digits=5, decimal_places=1, null=True, help_text="Home team Points Allowed PG last 10")
    away_papg_l10 = models.DecimalField(max_digits=5, decimal_places=1, null=True, help_text="Away team Points Allowed PG last 10")

    # Streaks
    home_streak = models.IntegerField(default=0, help_text="Home team streak (positive=wins)")
    away_streak = models.IntegerField(default=0, help_text="Away team streak (positive=wins)")

    # Rest days
    home_rest_days = models.IntegerField(default=2)
    away_rest_days = models.IntegerField(default=2)

    # Head-to-head this season before game
    h2h_home_wins = models.IntegerField(default=0)
    h2h_away_wins = models.IntegerField(default=0)

    # Home/away records going into game
    home_home_wins = models.IntegerField(default=0)
    home_home_losses = models.IntegerField(default=0)
    away_away_wins = models.IntegerField(default=0)
    away_away_losses = models.IntegerField(default=0)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['season']),
            models.Index(fields=['date']),
            models.Index(fields=['home_team_abbr', 'away_team_abbr']),
        ]

    def __str__(self):
        return f"{self.away_team_abbr} @ {self.home_team_abbr} ({self.date})"

    @property
    def total_score(self):
        return self.home_score + self.away_score

    @property
    def spread(self):
        """Actual spread (positive = home won by X)"""
        return self.home_score - self.away_score

    @property
    def home_won(self):
        return self.home_score > self.away_score
