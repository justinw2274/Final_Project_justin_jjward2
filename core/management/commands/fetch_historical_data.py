"""
Management command to fetch historical NBA game data for ML training.
Fetches multiple seasons from balldontlie.io API and calculates pre-game features.
"""
import requests
import time
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from django.core.management.base import BaseCommand
from core.models import HistoricalGame


class Command(BaseCommand):
    help = 'Fetches historical NBA game data for ML model training'

    BASE_URL = "https://api.balldontlie.io/v1"

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for balldontlie.io',
        )
        parser.add_argument(
            '--seasons',
            type=str,
            default='2019,2020,2021,2022,2023,2024',
            help='Comma-separated list of seasons to fetch (default: 2019-2024)',
        )
        parser.add_argument(
            '--skip-features',
            action='store_true',
            help='Skip calculating pre-game features (faster, raw data only)',
        )

    def handle(self, *args, **options):
        api_key = options.get('api_key')
        seasons_str = options.get('seasons', '2019,2020,2021,2022,2023,2024')
        skip_features = options.get('skip_features', False)

        seasons = [int(s.strip()) for s in seasons_str.split(',')]

        self.stdout.write(f"Fetching data for seasons: {seasons}")

        headers = {}
        if api_key:
            headers['Authorization'] = api_key

        total_games = 0

        for season in seasons:
            self.stdout.write(f"\nFetching season {season}-{season+1}...")
            games_fetched = self._fetch_season(season, headers)
            total_games += games_fetched
            self.stdout.write(self.style.SUCCESS(f"  Fetched {games_fetched} games"))

        self.stdout.write(f"\nTotal games fetched: {total_games}")

        if not skip_features:
            self.stdout.write("\nCalculating pre-game features...")
            self._calculate_features()
            self.stdout.write(self.style.SUCCESS("Features calculated!"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Total historical games in database: {HistoricalGame.objects.count()}"))

    def _fetch_season(self, season, headers):
        """Fetch all games for a season."""
        games_fetched = 0
        cursor = None

        while True:
            params = {
                'seasons[]': season,
                'per_page': 100,
            }
            if cursor:
                params['cursor'] = cursor

            try:
                response = requests.get(
                    f"{self.BASE_URL}/games",
                    headers=headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f"  API error: {e}"))
                break

            games = data.get('data', [])
            if not games:
                break

            for game in games:
                # Only process completed games
                if game.get('status') != 'Final':
                    continue

                home_score = game.get('home_team_score')
                away_score = game.get('visitor_team_score')

                # Skip games without scores
                if home_score is None or away_score is None:
                    continue

                try:
                    game_date = datetime.strptime(game['date'][:10], '%Y-%m-%d').date()

                    HistoricalGame.objects.update_or_create(
                        api_game_id=game['id'],
                        defaults={
                            'date': game_date,
                            'season': season,
                            'home_team_abbr': game['home_team']['abbreviation'],
                            'away_team_abbr': game['visitor_team']['abbreviation'],
                            'home_score': home_score,
                            'away_score': away_score,
                        }
                    )
                    games_fetched += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Skipping game {game.get('id')}: {e}"))
                    continue

            # Check for next page
            meta = data.get('meta', {})
            cursor = meta.get('next_cursor')
            if not cursor:
                break

            # Rate limiting - be nice to the API
            time.sleep(0.5)

        return games_fetched

    def _calculate_features(self):
        """Calculate pre-game features for all historical games."""
        # Get all games ordered by date
        games = HistoricalGame.objects.order_by('date').all()

        # Track team stats as we process games chronologically
        team_stats = defaultdict(lambda: {
            'wins': 0,
            'losses': 0,
            'home_wins': 0,
            'home_losses': 0,
            'away_wins': 0,
            'away_losses': 0,
            'recent_games': [],  # List of (date, points_scored, points_allowed, won)
            'streak': 0,
            'last_game_date': None,
        })

        # Track head-to-head by season
        h2h_by_season = defaultdict(lambda: defaultdict(lambda: {'home_wins': 0, 'away_wins': 0}))

        processed = 0
        total = games.count()

        for game in games:
            home = game.home_team_abbr
            away = game.away_team_abbr
            season = game.season

            home_stats = team_stats[home]
            away_stats = team_stats[away]

            # Get H2H key (sorted to be consistent)
            h2h_key = tuple(sorted([home, away]))
            h2h = h2h_by_season[season][h2h_key]

            # Calculate pre-game features (BEFORE updating with this game's result)

            # Win percentages
            home_games = home_stats['wins'] + home_stats['losses']
            away_games = away_stats['wins'] + away_stats['losses']
            game.home_win_pct = Decimal(str(round(home_stats['wins'] / home_games, 3))) if home_games > 0 else None
            game.away_win_pct = Decimal(str(round(away_stats['wins'] / away_games, 3))) if away_games > 0 else None

            # Rolling averages (last 10 games)
            home_recent = home_stats['recent_games'][-10:]
            away_recent = away_stats['recent_games'][-10:]

            if home_recent:
                game.home_ppg_l10 = Decimal(str(round(sum(g[1] for g in home_recent) / len(home_recent), 1)))
                game.home_papg_l10 = Decimal(str(round(sum(g[2] for g in home_recent) / len(home_recent), 1)))
            if away_recent:
                game.away_ppg_l10 = Decimal(str(round(sum(g[1] for g in away_recent) / len(away_recent), 1)))
                game.away_papg_l10 = Decimal(str(round(sum(g[2] for g in away_recent) / len(away_recent), 1)))

            # Streaks
            game.home_streak = home_stats['streak']
            game.away_streak = away_stats['streak']

            # Rest days
            if home_stats['last_game_date']:
                game.home_rest_days = min((game.date - home_stats['last_game_date']).days, 7)
            if away_stats['last_game_date']:
                game.away_rest_days = min((game.date - away_stats['last_game_date']).days, 7)

            # Head-to-head this season
            if h2h_key[0] == home:
                game.h2h_home_wins = h2h['home_wins']
                game.h2h_away_wins = h2h['away_wins']
            else:
                game.h2h_home_wins = h2h['away_wins']
                game.h2h_away_wins = h2h['home_wins']

            # Home/away records
            game.home_home_wins = home_stats['home_wins']
            game.home_home_losses = home_stats['home_losses']
            game.away_away_wins = away_stats['away_wins']
            game.away_away_losses = away_stats['away_losses']

            game.save()

            # NOW update stats with this game's result
            home_won = game.home_score > game.away_score

            if home_won:
                home_stats['wins'] += 1
                home_stats['home_wins'] += 1
                away_stats['losses'] += 1
                away_stats['away_losses'] += 1
                home_stats['streak'] = home_stats['streak'] + 1 if home_stats['streak'] >= 0 else 1
                away_stats['streak'] = away_stats['streak'] - 1 if away_stats['streak'] <= 0 else -1
                if h2h_key[0] == home:
                    h2h['home_wins'] += 1
                else:
                    h2h['away_wins'] += 1
            else:
                away_stats['wins'] += 1
                away_stats['away_wins'] += 1
                home_stats['losses'] += 1
                home_stats['home_losses'] += 1
                away_stats['streak'] = away_stats['streak'] + 1 if away_stats['streak'] >= 0 else 1
                home_stats['streak'] = home_stats['streak'] - 1 if home_stats['streak'] <= 0 else -1
                if h2h_key[0] == home:
                    h2h['away_wins'] += 1
                else:
                    h2h['home_wins'] += 1

            # Update recent games
            home_stats['recent_games'].append((game.date, game.home_score, game.away_score, home_won))
            away_stats['recent_games'].append((game.date, game.away_score, game.home_score, not home_won))

            # Keep only last 15 games in memory
            if len(home_stats['recent_games']) > 15:
                home_stats['recent_games'] = home_stats['recent_games'][-15:]
            if len(away_stats['recent_games']) > 15:
                away_stats['recent_games'] = away_stats['recent_games'][-15:]

            home_stats['last_game_date'] = game.date
            away_stats['last_game_date'] = game.date

            processed += 1
            if processed % 500 == 0:
                self.stdout.write(f"  Processed {processed}/{total} games...")

        self.stdout.write(f"  Processed {processed}/{total} games")
