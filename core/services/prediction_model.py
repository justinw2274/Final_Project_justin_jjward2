"""
NBA Game Prediction Model - Enhanced Version

A comprehensive research-based model for predicting NBA game outcomes.
Uses proven predictive features from academic research:

Sources:
- PMC Study (2024): XGBoost + SHAP analysis showed defensive rebounds as top predictor
- Dean Oliver's Four Factors: Explains ~80% of team success variance
- FiveThirtyEight: Elo + RAPTOR system
- Academic research: 66-74% typical accuracy, up to 85% with XGBoost

Features used (with research-backed weights):
1. Four Factors (eFG%, TOV%, ORB%, FTR) - ~30%
2. Elo Rating differential - ~20%
3. Net Rating (ORtg - DRtg) - ~15%
4. Home Court Advantage - ~8%
5. Rest/Schedule (B2B, 3-in-4) - ~7%
6. Win/Loss Streaks - ~5%
7. Head-to-Head history - ~5%
8. Rolling momentum (last 10 games) - ~5%
9. Strength of Schedule - ~5%

Data Leakage Prevention:
- Only uses data available BEFORE each game
- Pre-game snapshots stored for historical accuracy
- No future information used in predictions
"""
import math
from decimal import Decimal
from datetime import date, timedelta


class NBAPredictor:
    """
    Enhanced NBA Game Outcome Prediction Model

    Uses multiple proven predictive features with research-backed weights.
    Designed to achieve 70-75% prediction accuracy.
    """

    # Model weights (tuned based on research findings)
    WEIGHTS = {
        'four_factors': 0.30,      # Dean Oliver's proven framework
        'elo': 0.20,               # Dynamic rating system
        'net_rating': 0.15,        # Efficiency differential
        'home_court': 0.08,        # ~3.5 point advantage
        'schedule': 0.07,          # Rest, B2B, fatigue
        'streaks': 0.05,           # Momentum/psychology
        'h2h': 0.05,               # Head-to-head history
        'momentum': 0.05,          # Rolling performance
        'sos': 0.05,               # Strength of schedule
    }

    # Constants from research
    HOME_COURT_ELO_BONUS = 100     # ~64% implied win probability
    HOME_COURT_POINTS = 3.5       # Historical average
    B2B_PENALTY_POINTS = 1.5      # Back-to-back fatigue
    THREE_IN_FOUR_PENALTY = 2.0   # 3 games in 4 nights
    REST_ADVANTAGE_PER_DAY = 0.4  # Per extra rest day
    MAX_REST_ADVANTAGE = 2.5      # Cap the benefit

    # Elo system parameters
    ELO_K_FACTOR = 20
    ELO_HOME_ADVANTAGE = 100

    def __init__(self):
        self.league_avg_pace = 100.0
        self.league_avg_ortg = 114.0
        self.league_avg_drtg = 114.0

    def predict_game(self, home_team, away_team, game_date=None, game=None):
        """
        Generate a comprehensive prediction for a game.

        Args:
            home_team: Team model instance
            away_team: Team model instance
            game_date: Date of the game
            game: Optional Game instance with pre-computed schedule data

        Returns:
            tuple: (home_win_probability, confidence, predicted_spread)
        """
        if game_date is None:
            game_date = date.today()

        # Calculate individual component probabilities
        components = {}

        # 1. Four Factors (30%)
        components['four_factors'] = self._four_factors_probability(home_team, away_team)

        # 2. Elo Ratings (20%)
        components['elo'] = self._elo_probability(home_team, away_team)

        # 3. Net Rating (15%)
        components['net_rating'] = self._net_rating_probability(home_team, away_team)

        # 4. Home Court (8%)
        components['home_court'] = self._home_court_probability()

        # 5. Schedule/Rest (7%)
        components['schedule'] = self._schedule_probability(home_team, away_team, game_date, game)

        # 6. Streaks (5%)
        components['streaks'] = self._streak_probability(home_team, away_team)

        # 7. Head-to-Head (5%)
        components['h2h'] = self._h2h_probability(home_team, away_team, game)

        # 8. Momentum/Rolling (5%)
        components['momentum'] = self._momentum_probability(home_team, away_team)

        # 9. Strength of Schedule (5%)
        components['sos'] = self._sos_probability(home_team, away_team)

        # Combine probabilities using weighted average
        raw_prob = sum(
            components[key] * self.WEIGHTS[key]
            for key in self.WEIGHTS
        )

        # Normalize to 0.15-0.85 range (realistic bounds)
        home_win_prob = max(0.15, min(0.85, raw_prob))

        # Calculate confidence
        confidence = self._calculate_confidence(
            home_team, away_team, home_win_prob, components
        )

        # Calculate spread
        spread = self._calculate_spread(
            home_team, away_team, home_win_prob, game_date, game
        )

        return (
            Decimal(str(round(home_win_prob * 100, 2))),
            Decimal(str(round(confidence, 2))),
            Decimal(str(round(spread, 1)))
        )

    def _four_factors_probability(self, home_team, away_team):
        """
        Calculate win probability based on Dean Oliver's Four Factors.
        Research shows these explain ~80% of team success.

        Weights: eFG% (40%), TOV% (25%), ORB% (20%), FT Rate (15%)
        """
        # Home team offensive efficiency
        home_off = self._calc_four_factors_score(
            float(home_team.efg_pct),
            float(home_team.tov_pct),
            float(home_team.orb_pct),
            float(home_team.ft_rate)
        )

        # Home team defensive efficiency (opponent's factors)
        home_def = self._calc_four_factors_score(
            float(home_team.opp_efg_pct),
            float(home_team.opp_tov_pct),
            float(home_team.opp_orb_pct),
            float(home_team.opp_ft_rate)
        )

        # Away team offensive/defensive
        away_off = self._calc_four_factors_score(
            float(away_team.efg_pct),
            float(away_team.tov_pct),
            float(away_team.orb_pct),
            float(away_team.ft_rate)
        )
        away_def = self._calc_four_factors_score(
            float(away_team.opp_efg_pct),
            float(away_team.opp_tov_pct),
            float(away_team.opp_orb_pct),
            float(away_team.opp_ft_rate)
        )

        # Net advantage: (home offense vs away defense) - (away offense vs home defense)
        home_advantage = (home_off - away_def) - (away_off - home_def)

        return self._logistic(home_advantage * 5)

    def _calc_four_factors_score(self, efg, tov, orb, ftr):
        """Calculate weighted Four Factors score."""
        return (
            efg * 0.40 +
            (1 - tov) * 0.25 +
            orb * 0.20 +
            ftr * 0.15
        )

    def _elo_probability(self, home_team, away_team):
        """
        Elo-based win probability.
        Formula: P = 1 / (1 + 10^((Rb - Ra) / 400))
        """
        home_elo = float(home_team.elo_rating) + self.ELO_HOME_ADVANTAGE
        away_elo = float(away_team.elo_rating)

        elo_diff = home_elo - away_elo
        return 1 / (1 + math.pow(10, -elo_diff / 400))

    def _net_rating_probability(self, home_team, away_team):
        """
        Net Rating differential probability.
        Each point of net rating ≈ 2.5% win probability.
        """
        home_net = home_team.net_rating
        away_net = away_team.net_rating

        net_diff = (home_net - away_net) + self.HOME_COURT_POINTS
        return self._logistic(net_diff * 0.08)

    def _home_court_probability(self):
        """Base home court advantage: ~54% historically."""
        return 0.54

    def _schedule_probability(self, home_team, away_team, game_date, game=None):
        """
        Schedule and rest advantage probability.

        Factors:
        - Days of rest differential
        - Back-to-back games
        - 3 games in 4 nights
        """
        if game:
            home_rest = game.home_rest_days
            away_rest = game.away_rest_days
            home_b2b = game.home_b2b
            away_b2b = game.away_b2b
            home_3in4 = game.home_3in4
            away_3in4 = game.away_3in4
        else:
            home_rest = self._calc_rest_days(home_team, game_date)
            away_rest = self._calc_rest_days(away_team, game_date)
            home_b2b = home_rest == 1
            away_b2b = away_rest == 1
            home_3in4 = False
            away_3in4 = False

        # Calculate point advantage from schedule
        schedule_advantage = 0.0

        # Rest differential
        rest_diff = min(home_rest, 5) - min(away_rest, 5)
        schedule_advantage += rest_diff * self.REST_ADVANTAGE_PER_DAY

        # B2B penalties
        if home_b2b:
            schedule_advantage -= self.B2B_PENALTY_POINTS
        if away_b2b:
            schedule_advantage += self.B2B_PENALTY_POINTS

        # 3-in-4 penalties
        if home_3in4:
            schedule_advantage -= self.THREE_IN_FOUR_PENALTY
        if away_3in4:
            schedule_advantage += self.THREE_IN_FOUR_PENALTY

        # Cap the advantage
        schedule_advantage = max(-self.MAX_REST_ADVANTAGE * 2,
                                 min(self.MAX_REST_ADVANTAGE * 2, schedule_advantage))

        # Convert to probability (centered at 0.5)
        return 0.5 + (schedule_advantage * 0.025)

    def _calc_rest_days(self, team, game_date):
        """Calculate days of rest for a team."""
        if team.last_game_date is None:
            return 3
        rest = (game_date - team.last_game_date).days
        return max(1, min(rest, 7))

    def _streak_probability(self, home_team, away_team):
        """
        Win/loss streak impact on probability.
        Psychology and momentum factor.
        """
        home_streak = int(home_team.current_streak) if home_team.current_streak else 0
        away_streak = int(away_team.current_streak) if away_team.current_streak else 0

        # Diminishing returns for long streaks
        home_factor = math.tanh(home_streak / 5) * 0.1
        away_factor = math.tanh(away_streak / 5) * 0.1

        streak_diff = home_factor - away_factor
        return 0.5 + streak_diff

    def _h2h_probability(self, home_team, away_team, game=None):
        """
        Head-to-head history probability.
        Uses season matchup record if available.
        """
        if game and (game.h2h_home_wins or game.h2h_away_wins):
            total = game.h2h_home_wins + game.h2h_away_wins
            if total > 0:
                h2h_pct = game.h2h_home_wins / total
                # Weight by games played (more games = more reliable)
                weight = min(total / 4, 1.0)
                return 0.5 + (h2h_pct - 0.5) * weight

        # Default to neutral if no H2H data
        return 0.5

    def _momentum_probability(self, home_team, away_team):
        """
        Rolling performance momentum.
        Uses recent trends in scoring and defense.
        """
        # Scoring trend differential
        home_pts_trend = float(home_team.points_trend) if home_team.points_trend else 0
        away_pts_trend = float(away_team.points_trend) if away_team.points_trend else 0

        # Defense trend (negative = improving)
        home_def_trend = float(home_team.defense_trend) if home_team.defense_trend else 0
        away_def_trend = float(away_team.defense_trend) if away_team.defense_trend else 0

        # Combined momentum (positive offensive + negative defensive = good)
        home_momentum = home_pts_trend - home_def_trend
        away_momentum = away_pts_trend - away_def_trend

        momentum_diff = home_momentum - away_momentum

        # Convert to probability
        return self._logistic(momentum_diff * 0.5)

    def _sos_probability(self, home_team, away_team):
        """
        Strength of schedule adjustment.
        Teams with harder schedules may be underrated.
        """
        home_sos = float(home_team.strength_of_schedule) if home_team.strength_of_schedule else 0.5
        away_sos = float(away_team.strength_of_schedule) if away_team.strength_of_schedule else 0.5

        # If team has had harder schedule, slight boost
        sos_diff = home_sos - away_sos

        # Small adjustment based on SOS differential
        return 0.5 + (sos_diff * 0.2)

    def _calculate_confidence(self, home_team, away_team, home_win_prob, components):
        """
        Calculate model confidence in the prediction.

        Higher confidence when:
        - Win probability far from 50%
        - Multiple models agree
        - Large quality differential
        """
        # Base confidence from probability distance
        prob_distance = abs(home_win_prob - 0.5) * 2
        base_confidence = 50 + (prob_distance * 35)

        # Agreement bonus
        probs = list(components.values())
        avg_prob = sum(probs) / len(probs)
        variance = sum((p - avg_prob) ** 2 for p in probs) / len(probs)
        agreement_bonus = max(0, 12 - (variance * 150))

        # Quality difference bonus
        elo_diff = abs(float(home_team.elo_rating) - float(away_team.elo_rating))
        quality_bonus = min(12, elo_diff / 40)

        # Games played penalty (less data = less confidence)
        games_played = (home_team.wins + home_team.losses + away_team.wins + away_team.losses) / 2
        data_factor = min(1.0, games_played / 20)

        confidence = (base_confidence + agreement_bonus + quality_bonus) * data_factor

        return max(40, min(92, confidence))

    def _calculate_spread(self, home_team, away_team, home_win_prob, game_date, game=None):
        """
        Calculate predicted point spread.
        """
        # Base from net rating
        net_diff = home_team.net_rating - away_team.net_rating

        # Pace adjustment
        avg_pace = (float(home_team.pace) + float(away_team.pace)) / 2
        pace_factor = avg_pace / self.league_avg_pace

        # Base spread
        spread = (net_diff * pace_factor) + self.HOME_COURT_POINTS

        # Schedule adjustment
        if game:
            if game.home_b2b:
                spread -= self.B2B_PENALTY_POINTS
            if game.away_b2b:
                spread += self.B2B_PENALTY_POINTS
            rest_diff = game.home_rest_days - game.away_rest_days
            spread += rest_diff * self.REST_ADVANTAGE_PER_DAY * 0.5

        # Streak adjustment (small)
        home_streak = int(home_team.current_streak) if home_team.current_streak else 0
        away_streak = int(away_team.current_streak) if away_team.current_streak else 0
        spread += (home_streak - away_streak) * 0.2

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
        Uses margin of victory adjustment.
        """
        winner_is_home = winner == home_team

        if winner_is_home:
            winner_elo = float(winner.elo_rating) + self.ELO_HOME_ADVANTAGE
            loser_elo = float(loser.elo_rating)
        else:
            winner_elo = float(winner.elo_rating)
            loser_elo = float(loser.elo_rating) + self.ELO_HOME_ADVANTAGE

        expected = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))

        # Margin of victory multiplier
        mov_mult = math.log(max(margin, 1) + 1) * (2.2 / ((winner_elo - loser_elo) * 0.001 + 2.2))
        mov_mult = max(1.0, min(mov_mult, 2.5))

        elo_change = self.ELO_K_FACTOR * mov_mult * (1 - expected)

        winner.elo_rating = Decimal(str(round(float(winner.elo_rating) + elo_change, 1)))
        loser.elo_rating = Decimal(str(round(float(loser.elo_rating) - elo_change, 1)))

        return elo_change


def predict_game(home_team, away_team, game_date=None, game=None):
    """Convenience function for predictions."""
    predictor = NBAPredictor()
    return predictor.predict_game(home_team, away_team, game_date, game)
