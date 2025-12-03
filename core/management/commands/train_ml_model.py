"""
Management command to train ML models for NBA game predictions.
Trains separate models for predicting spread and total score.
"""
import numpy as np
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

from core.models import HistoricalGame


class Command(BaseCommand):
    help = 'Train ML models for NBA game predictions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            type=str,
            default='ridge',
            choices=['ridge', 'gbr'],
            help='Model type: ridge (linear) or gbr (gradient boosting)',
        )
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.2,
            help='Fraction of data to use for testing',
        )

    def handle(self, *args, **options):
        model_type = options['model_type']
        test_size = options['test_size']

        self.stdout.write(f"Training {model_type} models...")
        self.stdout.write(f"Test size: {test_size * 100:.0f}%")

        # Prepare data
        X, y_spread, y_total, feature_names = self._prepare_data()

        self.stdout.write(f"\nDataset: {len(X)} samples, {len(feature_names)} features")
        self.stdout.write(f"Features: {', '.join(feature_names)}")

        # Split data
        X_train, X_test, y_spread_train, y_spread_test, y_total_train, y_total_test = train_test_split(
            X, y_spread, y_total, test_size=test_size, random_state=42
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train spread model
        self.stdout.write("\n--- Training SPREAD Model ---")
        spread_model = self._train_model(model_type, X_train_scaled, y_spread_train)
        spread_metrics = self._evaluate_model(spread_model, X_test_scaled, y_spread_test, "Spread")

        # Train total model
        self.stdout.write("\n--- Training TOTAL Model ---")
        total_model = self._train_model(model_type, X_train_scaled, y_total_train)
        total_metrics = self._evaluate_model(total_model, X_test_scaled, y_total_test, "Total")

        # Cross-validation
        self.stdout.write("\n--- Cross-Validation (5-fold) ---")
        spread_cv = cross_val_score(spread_model, X_train_scaled, y_spread_train, cv=5, scoring='neg_mean_absolute_error')
        total_cv = cross_val_score(total_model, X_train_scaled, y_total_train, cv=5, scoring='neg_mean_absolute_error')
        self.stdout.write(f"Spread CV MAE: {-spread_cv.mean():.2f} (+/- {spread_cv.std() * 2:.2f})")
        self.stdout.write(f"Total CV MAE: {-total_cv.mean():.2f} (+/- {total_cv.std() * 2:.2f})")

        # Feature importance (for tree-based models)
        if model_type == 'gbr':
            self.stdout.write("\n--- Feature Importance ---")
            importances = list(zip(feature_names, spread_model.feature_importances_))
            importances.sort(key=lambda x: x[1], reverse=True)
            for name, imp in importances[:10]:
                self.stdout.write(f"  {name}: {imp:.3f}")

        # Save models
        model_dir = settings.BASE_DIR / 'core' / 'ml_models'
        model_dir.mkdir(exist_ok=True)

        joblib.dump(spread_model, model_dir / 'spread_model.joblib')
        joblib.dump(total_model, model_dir / 'total_model.joblib')
        joblib.dump(scaler, model_dir / 'scaler.joblib')
        joblib.dump(feature_names, model_dir / 'feature_names.joblib')

        self.stdout.write(self.style.SUCCESS(f"\nModels saved to {model_dir}/"))

        # Show model sizes
        import os
        total_size = 0
        for f in model_dir.glob('*.joblib'):
            size = os.path.getsize(f) / 1024
            total_size += size
            self.stdout.write(f"  {f.name}: {size:.1f} KB")
        self.stdout.write(f"  Total: {total_size:.1f} KB")

    def _prepare_data(self):
        """Prepare features and targets from historical games."""
        games = HistoricalGame.objects.filter(
            home_win_pct__isnull=False,
            away_win_pct__isnull=False,
            home_ppg_l10__isnull=False,
            away_ppg_l10__isnull=False,
        ).order_by('date')

        X = []
        y_spread = []
        y_total = []

        for game in games:
            features = [
                # Win percentages
                float(game.home_win_pct),
                float(game.away_win_pct),
                float(game.home_win_pct) - float(game.away_win_pct),  # Win pct diff

                # Scoring (last 10)
                float(game.home_ppg_l10),
                float(game.away_ppg_l10),
                float(game.home_ppg_l10) - float(game.away_ppg_l10),  # PPG diff

                # Defense (last 10)
                float(game.home_papg_l10) if game.home_papg_l10 else 110.0,
                float(game.away_papg_l10) if game.away_papg_l10 else 110.0,

                # Net ratings (offense - defense)
                float(game.home_ppg_l10) - float(game.home_papg_l10 or 110),
                float(game.away_ppg_l10) - float(game.away_papg_l10 or 110),

                # Streaks
                game.home_streak,
                game.away_streak,
                game.home_streak - game.away_streak,  # Streak diff

                # Rest
                game.home_rest_days,
                game.away_rest_days,
                game.home_rest_days - game.away_rest_days,  # Rest advantage

                # Home/away records
                game.home_home_wins / max(game.home_home_wins + game.home_home_losses, 1),
                game.away_away_wins / max(game.away_away_wins + game.away_away_losses, 1),

                # Head-to-head
                game.h2h_home_wins / max(game.h2h_home_wins + game.h2h_away_wins, 1) if (game.h2h_home_wins + game.h2h_away_wins) > 0 else 0.5,

                # Combined scoring potential (for total prediction)
                (float(game.home_ppg_l10) + float(game.away_ppg_l10)) / 2,

                # Combined defensive strength (lower = better)
                (float(game.home_papg_l10 or 110) + float(game.away_papg_l10 or 110)) / 2,
            ]

            X.append(features)
            y_spread.append(game.home_score - game.away_score)  # Actual spread
            y_total.append(game.home_score + game.away_score)   # Actual total

        feature_names = [
            'home_win_pct', 'away_win_pct', 'win_pct_diff',
            'home_ppg_l10', 'away_ppg_l10', 'ppg_diff',
            'home_papg_l10', 'away_papg_l10',
            'home_net_rating', 'away_net_rating',
            'home_streak', 'away_streak', 'streak_diff',
            'home_rest', 'away_rest', 'rest_diff',
            'home_home_win_pct', 'away_away_win_pct',
            'h2h_home_pct',
            'avg_ppg', 'avg_papg',
        ]

        return np.array(X), np.array(y_spread), np.array(y_total), feature_names

    def _train_model(self, model_type, X_train, y_train):
        """Train a model of the specified type."""
        if model_type == 'ridge':
            model = Ridge(alpha=1.0)
        else:  # gbr
            model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )

        model.fit(X_train, y_train)
        return model

    def _evaluate_model(self, model, X_test, y_test, name):
        """Evaluate model performance."""
        y_pred = model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        self.stdout.write(f"{name} Model Performance:")
        self.stdout.write(f"  MAE:  {mae:.2f} points")
        self.stdout.write(f"  RMSE: {rmse:.2f} points")
        self.stdout.write(f"  R²:   {r2:.3f}")

        # Show some sample predictions
        self.stdout.write(f"  Sample predictions vs actual:")
        for i in range(min(5, len(y_test))):
            self.stdout.write(f"    Predicted: {y_pred[i]:.1f}, Actual: {y_test[i]:.0f}")

        return {'mae': mae, 'rmse': rmse, 'r2': r2}
