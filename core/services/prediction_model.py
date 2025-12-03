"""
NBA Game Prediction Model

A research-based statistical model for predicting NBA game outcomes.
Based on proven predictive features including:
- Dean Oliver's Four Factors (eFG%, TOV%, ORB%, FTR)
- Efficiency Ratings (Offensive/Defensive Rating)
- Elo Rating System
- Home Court Advantage
- Rest/Schedule Factors
- Recent Form (Last 10 games)

Research shows these features can achieve 70-85% prediction accuracy.
"""
import math
from decimal import Decimal
from datetime import date, timedelta


class NBAPredictor:
    """
    NBA Game Outcome Prediction Model

    Uses a weighted combination of proven predictive features:
    - Four Factors: ~40% of prediction weight
    - Elo Ratings: ~25% of prediction weight
    - Net Rating: ~20% of prediction weight
    - Home Court + Rest: ~15% of prediction weight
    """

    # Model weights (tuned based on research findings)
    WEIGHTS = {
        'four_factors': 0.35,
        'elo': 0.25,
        'net_rating': 0.25,
        'home_court': 0.10,
        'rest': 0.05,
    }

    # Home court advantage parameters
    HOME_COURT_ELO_BONUS = 100  # ~64% win probability boost
    HOME_COURT_POINTS = 3.5     # Historical average home advantage in points

    # Elo system parameters
    ELO_K_FACTOR = 20           # How quickly ratings change
    ELO_HOME_ADVANTAGE = 100    # Elo points added for home team

    # Rest day impact (points per day of rest advantage)
    REST_IMPACT_PER_DAY = 0.35
    MAX_REST_IMPACT = 2.0       # Cap the rest advantage

    def __init__(self):
        self.league_avg_pace = 100.0
        self.league_avg_ortg = 114.0
        self.league_avg_drtg = 114.0

    def predict_game(self, home_team, away_team, game_date=None):
        """
        Generate a comprehensive prediction for a game.

        Returns:
            tuple: (home_win_probability, confidence, predicted_spread)
        """
        if game_date is None:
            game_date = date.today()

        # Calculate individual components
        four_factors_prob = self._four_factors_probability(home_team, away_team)
        elo_prob = self._elo_probability(home_team, away_team)
        net_rating_prob = self._net_rating_probability(home_team, away_team)
        home_court_prob = self._home_court_probability()
        rest_prob = self._rest_probability(home_team, away_team, game_date)

        # Combine probabilities using weighted average
        raw_prob = (
            four_factors_prob * self.WEIGHTS['four_factors'] +
            elo_prob * self.WEIGHTS['elo'] +
            net_rating_prob * self.WEIGHTS['net_rating'] +
            home_court_prob * self.WEIGHTS['home_court'] +
            rest_prob * self.WEIGHTS['rest']
        )

        # Normalize to ensure probability is between 0.15 and 0.85
        # (no team realistically has >85% or <15% chance)
        home_win_prob = max(0.15, min(0.85, raw_prob))

        # Calculate confidence based on how decisive the prediction is
        confidence = self._calculate_confidence(
            home_team, away_team, home_win_prob,
            four_factors_prob, elo_prob, net_rating_prob
        )

        # Calculate predicted spread
        spread = self._calculate_spread(
            home_team, away_team, home_win_prob, game_date
        )

        return (
            Decimal(str(round(home_win_prob * 100, 2))),
            Decimal(str(round(confidence, 2))),
            Decimal(str(round(spread, 1)))
        )

    def _four_factors_probability(self, home_team, away_team):
        """
        Calculate win probability based on Dean Oliver's Four Factors.

        Four Factors weights (offense):
        - eFG%: 40%
        - TOV%: 25% (lower is better)
        - ORB%: 20%
        - FT Rate: 15%
        """
        # Calculate offensive score for each team
        home_off = self._calc_four_factors_score(
            float(home_team.efg_pct),
            float(home_team.tov_pct),
            float(home_team.orb_pct),
            float(home_team.ft_rate)
        )
        away_off = self._calc_four_factors_score(
            float(away_team.efg_pct),
            float(away_team.tov_pct),
            float(away_team.orb_pct),
            float(away_team.ft_rate)
        )

        # Calculate defensive score (using opponent stats)
        home_def = self._calc_four_factors_score(
            float(home_team.opp_efg_pct),
            float(home_team.opp_tov_pct),
            float(home_team.opp_orb_pct),
            float(home_team.opp_ft_rate)
        )
        away_def = self._calc_four_factors_score(
            float(away_team.opp_efg_pct),
            float(away_team.opp_tov_pct),
            float(away_team.opp_orb_pct),
            float(away_team.opp_ft_rate)
        )

        # Home team advantage: their offense vs away defense,
        # and away offense vs home defense
        home_advantage = (home_off - away_def) - (away_off - home_def)

        # Convert to probability using logistic function
        # Scale factor tuned to match historical data
        return self._logistic(home_advantage * 5)

    def _calc_four_factors_score(self, efg, tov, orb, ftr):
        """Calculate weighted Four Factors score."""
        return (
            efg * 0.40 +
            (1 - tov) * 0.25 +  # Lower turnover rate is better
            orb * 0.20 +
            ftr * 0.15
        )

    def _elo_probability(self, home_team, away_team):
        """
        Calculate win probability using Elo rating system.

        Formula: P(A wins) = 1 / (1 + 10^((Rb - Ra) / 400))
        With home court adjustment of ~100 Elo points.
        """
        home_elo = float(home_team.elo_rating) + self.ELO_HOME_ADVANTAGE
        away_elo = float(away_team.elo_rating)

        elo_diff = home_elo - away_elo
        probability = 1 / (1 + math.pow(10, -elo_diff / 400))

        return probability

    def _net_rating_probability(self, home_team, away_team):
        """
        Calculate win probability based on Net Rating differential.

        Net Rating = Offensive Rating - Defensive Rating
        Represents points per 100 possessions above/below average.
        """
        home_net = home_team.net_rating
        away_net = away_team.net_rating

        # Add home court advantage (~3.5 points)
        net_diff = (home_net - away_net) + self.HOME_COURT_POINTS

        # Convert to probability
        # Each point of net rating difference ≈ 2.5% win probability
        return self._logistic(net_diff * 0.08)

    def _home_court_probability(self):
        """
        Base home court advantage probability.
        Historical NBA average: ~57-60% for home teams (declining to ~54% recently).
        """
        return 0.54

    def _rest_probability(self, home_team, away_team, game_date):
        """
        Calculate rest advantage impact on win probability.

        Research shows:
        - Back-to-back games reduce performance by 0.5-2.0 points
        - Each extra day of rest adds ~0.35 to net rating
        """
        home_rest = self._calculate_rest_days(home_team, game_date)
        away_rest = self._calculate_rest_days(away_team, game_date)

        rest_diff = home_rest - away_rest

        # Cap the impact
        rest_impact = max(-self.MAX_REST_IMPACT,
                         min(self.MAX_REST_IMPACT,
                             rest_diff * self.REST_IMPACT_PER_DAY))

        # Convert to probability (centered at 0.5)
        return 0.5 + (rest_impact * 0.02)

    def _calculate_rest_days(self, team, game_date):
        """Calculate days of rest for a team."""
        if team.last_game_date is None:
            return 2  # Default assumption

        rest = (game_date - team.last_game_date).days
        return min(rest, 7)  # Cap at 7 days

    def _calculate_confidence(self, home_team, away_team, home_win_prob,
                             ff_prob, elo_prob, nr_prob):
        """
        Calculate model confidence in the prediction.

        Higher confidence when:
        - Win probability is far from 50%
        - Multiple models agree
        - Teams have significant quality difference
        """
        # Base confidence from how decisive the prediction is
        prob_distance = abs(home_win_prob - 0.5) * 2
        base_confidence = 50 + (prob_distance * 40)

        # Agreement bonus: how much do different models agree?
        predictions = [ff_prob, elo_prob, nr_prob]
        avg_pred = sum(predictions) / len(predictions)
        variance = sum((p - avg_pred) ** 2 for p in predictions) / len(predictions)
        agreement_bonus = max(0, 10 - (variance * 100))

        # Quality difference bonus
        elo_diff = abs(float(home_team.elo_rating) - float(away_team.elo_rating))
        quality_bonus = min(15, elo_diff / 50)

        confidence = base_confidence + agreement_bonus + quality_bonus

        return max(40, min(95, confidence))

    def _calculate_spread(self, home_team, away_team, home_win_prob, game_date):
        """
        Calculate predicted point spread.

        Uses multiple factors:
        - Net rating differential
        - Pace (affects total points)
        - Home court advantage
        - Rest differential
        """
        # Base spread from net rating differential
        net_diff = home_team.net_rating - away_team.net_rating

        # Adjust for pace (higher pace = more variance)
        avg_pace = (float(home_team.pace) + float(away_team.pace)) / 2
        pace_factor = avg_pace / self.league_avg_pace

        # Home court advantage
        spread = (net_diff * pace_factor) + self.HOME_COURT_POINTS

        # Rest adjustment
        home_rest = self._calculate_rest_days(home_team, game_date)
        away_rest = self._calculate_rest_days(away_team, game_date)
        rest_diff = home_rest - away_rest
        spread += rest_diff * self.REST_IMPACT_PER_DAY

        # Cap spread at reasonable values
        return max(-25, min(25, spread))

    def _logistic(self, x):
        """Logistic function to convert values to probability."""
        try:
            return 1 / (1 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def update_elo_after_game(self, winner, loser, home_team, margin):
        """
        Update Elo ratings after a game result.

        Uses margin of victory adjustment for more accurate ratings.
        """
        # Determine if winner was home team
        winner_is_home = winner == home_team

        # Get current ratings with home adjustment
        if winner_is_home:
            winner_elo = float(winner.elo_rating) + self.ELO_HOME_ADVANTAGE
            loser_elo = float(loser.elo_rating)
        else:
            winner_elo = float(winner.elo_rating)
            loser_elo = float(loser.elo_rating) + self.ELO_HOME_ADVANTAGE

        # Expected score for winner
        expected = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))

        # Margin of victory multiplier (diminishing returns for blowouts)
        mov_mult = math.log(max(margin, 1) + 1) * (2.2 / ((winner_elo - loser_elo) * 0.001 + 2.2))
        mov_mult = max(1.0, min(mov_mult, 3.0))

        # Calculate Elo change
        elo_change = self.ELO_K_FACTOR * mov_mult * (1 - expected)

        # Update ratings
        winner.elo_rating = Decimal(str(round(float(winner.elo_rating) + elo_change, 1)))
        loser.elo_rating = Decimal(str(round(float(loser.elo_rating) - elo_change, 1)))

        return elo_change


def predict_game(home_team, away_team, game_date=None):
    """
    Convenience function to generate a prediction.

    Returns:
        tuple: (home_win_probability, confidence, predicted_spread)
    """
    predictor = NBAPredictor()
    return predictor.predict_game(home_team, away_team, game_date)
