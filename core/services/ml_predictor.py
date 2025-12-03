"""
ML-based NBA Game Predictor

Uses trained machine learning models to predict game spreads and totals.
Falls back to heuristic model if ML models are not available.
"""
import os
import numpy as np
from decimal import Decimal
from pathlib import Path

try:
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class MLPredictor:
    """
    Machine Learning based NBA game predictor.

    Uses Gradient Boosting models trained on historical NBA data
    to predict game spread and total score.
    """

    def __init__(self, model_dir=None):
        """
        Initialize the ML predictor.

        Args:
            model_dir: Path to directory containing trained models.
                      Defaults to core/ml_models/
        """
        self.models_loaded = False
        self.spread_model = None
        self.total_model = None
        self.scaler = None
        self.feature_names = None

        if not ML_AVAILABLE:
            return

        if model_dir is None:
            # Default path relative to this file
            model_dir = Path(__file__).parent.parent / 'ml_models'
        else:
            model_dir = Path(model_dir)

        self._load_models(model_dir)

    def _load_models(self, model_dir):
        """Load trained models from disk."""
        try:
            self.spread_model = joblib.load(model_dir / 'spread_model.joblib')
            self.total_model = joblib.load(model_dir / 'total_model.joblib')
            self.scaler = joblib.load(model_dir / 'scaler.joblib')
            self.feature_names = joblib.load(model_dir / 'feature_names.joblib')
            self.models_loaded = True
        except Exception as e:
            print(f"Warning: Could not load ML models: {e}")
            self.models_loaded = False

    def predict(self, home_team, away_team, game=None):
        """
        Predict game spread and total using ML models.

        Args:
            home_team: Team model instance (home team)
            away_team: Team model instance (away team)
            game: Optional Game instance with additional context

        Returns:
            tuple: (predicted_spread, predicted_total, home_score, away_score)
                   or None if models not available
        """
        if not self.models_loaded:
            return None

        # Prepare features
        features = self._prepare_features(home_team, away_team, game)
        if features is None:
            return None

        # Scale features
        features_scaled = self.scaler.transform([features])

        # Predict
        spread = float(self.spread_model.predict(features_scaled)[0])
        total = float(self.total_model.predict(features_scaled)[0])

        # Cap spread at realistic limits
        spread = max(-16, min(16, spread))

        # Calculate individual team scores from spread and total
        half_total = total / 2
        home_score = round(half_total + spread / 2)
        away_score = round(half_total - spread / 2)

        # Ensure realistic bounds
        home_score = max(95, min(135, home_score))
        away_score = max(95, min(135, away_score))

        # Recalculate spread from rounded scores to ensure consistency
        # This way the displayed spread always matches the displayed score differential
        actual_spread = home_score - away_score
        actual_total = home_score + away_score

        return (
            Decimal(str(float(actual_spread))),
            Decimal(str(float(actual_total))),
            home_score,
            away_score
        )

    def _prepare_features(self, home_team, away_team, game=None):
        """
        Prepare feature vector for prediction.

        Uses team statistics to create features matching the training data.
        """
        try:
            # Win percentages
            home_games = home_team.wins + home_team.losses
            away_games = away_team.wins + away_team.losses

            home_win_pct = home_team.wins / home_games if home_games > 0 else 0.5
            away_win_pct = away_team.wins / away_games if away_games > 0 else 0.5

            # Scoring averages (use as proxy for L10 since we have avg_points_scored)
            home_ppg = float(home_team.avg_points_scored) if home_team.avg_points_scored else 110.0
            away_ppg = float(away_team.avg_points_scored) if away_team.avg_points_scored else 110.0

            home_papg = float(home_team.avg_points_allowed) if home_team.avg_points_allowed else 110.0
            away_papg = float(away_team.avg_points_allowed) if away_team.avg_points_allowed else 110.0

            # Net ratings
            home_net = home_ppg - home_papg
            away_net = away_ppg - away_papg

            # Streaks
            home_streak = int(home_team.current_streak) if home_team.current_streak else 0
            away_streak = int(away_team.current_streak) if away_team.current_streak else 0

            # Rest days
            if game:
                home_rest = game.home_rest_days
                away_rest = game.away_rest_days
            else:
                home_rest = 2
                away_rest = 2

            # Home/away records - use overall win pct as proxy
            home_home_win_pct = home_win_pct  # Could be improved with actual home record
            away_away_win_pct = away_win_pct

            # H2H - use 0.5 if not available
            if game and (game.h2h_home_wins + game.h2h_away_wins) > 0:
                h2h_home_pct = game.h2h_home_wins / (game.h2h_home_wins + game.h2h_away_wins)
            else:
                h2h_home_pct = 0.5

            features = [
                home_win_pct,
                away_win_pct,
                home_win_pct - away_win_pct,  # win_pct_diff
                home_ppg,
                away_ppg,
                home_ppg - away_ppg,  # ppg_diff
                home_papg,
                away_papg,
                home_net,  # home_net_rating
                away_net,  # away_net_rating
                home_streak,
                away_streak,
                home_streak - away_streak,  # streak_diff
                home_rest,
                away_rest,
                home_rest - away_rest,  # rest_diff
                home_home_win_pct,
                away_away_win_pct,
                h2h_home_pct,
                (home_ppg + away_ppg) / 2,  # avg_ppg
                (home_papg + away_papg) / 2,  # avg_papg
            ]

            return features

        except Exception as e:
            print(f"Error preparing features: {e}")
            return None

    def calculate_win_probability(self, spread):
        """
        Convert spread to win probability.

        Based on historical data, each point of spread ≈ 3% win probability.
        """
        # Logistic conversion from spread to probability
        # Home team favored by 7 points ≈ 70% win probability
        prob = 1 / (1 + np.exp(-spread / 4.5))
        return Decimal(str(round(prob * 100, 2)))

    def calculate_confidence(self, spread, home_team, away_team):
        """
        Calculate model confidence based on quality differential and spread magnitude.
        """
        # Base confidence from spread magnitude
        spread_confidence = min(abs(spread) * 2 + 40, 85)

        # Adjust based on team quality (games played)
        home_games = home_team.wins + home_team.losses
        away_games = away_team.wins + away_team.losses
        games_factor = min((home_games + away_games) / 40, 1.0)

        confidence = spread_confidence * games_factor
        return Decimal(str(round(max(40, min(90, confidence)), 2)))


def get_ml_predictor():
    """Get or create the ML predictor singleton."""
    if not hasattr(get_ml_predictor, '_instance'):
        get_ml_predictor._instance = MLPredictor()
    return get_ml_predictor._instance
