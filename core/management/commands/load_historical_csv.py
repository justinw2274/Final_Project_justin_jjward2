"""
Management command to load historical NBA game data from CSV.
Processes the NBA-Data-2010-2024 dataset.
"""
import csv
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import HistoricalGame


class Command(BaseCommand):
    help = 'Load historical NBA game data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/nba_games_2010_2024.csv',
            help='Path to CSV file (relative to project root)',
        )
        parser.add_argument(
            '--min-season',
            type=int,
            default=2018,
            help='Minimum season to load (default: 2018 for last 6 seasons)',
        )

    def handle(self, *args, **options):
        file_path = settings.BASE_DIR / options['file']
        min_season = options['min_season']

        self.stdout.write(f"Loading data from {file_path}")
        self.stdout.write(f"Including seasons >= {min_season}")

        # Read and process the CSV
        games_by_id = defaultdict(dict)

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Parse season year (e.g., "2022-23" -> 2022)
                season_str = row['SEASON_YEAR']
                try:
                    season = int(season_str.split('-')[0])
                except (ValueError, IndexError):
                    continue

                if season < min_season:
                    continue

                game_id = row['GAME_ID']
                matchup = row['MATCHUP']
                team_abbr = row['TEAM_ABBREVIATION']
                points = int(row['PTS']) if row['PTS'] else 0
                game_date = row['GAME_DATE'][:10]  # Just the date part

                # Determine if home or away from matchup string
                # "GSW vs. PHX" = GSW is home
                # "GSW @ PHX" = GSW is away
                is_home = ' vs. ' in matchup

                if game_id not in games_by_id:
                    games_by_id[game_id] = {
                        'date': game_date,
                        'season': season,
                    }

                if is_home:
                    games_by_id[game_id]['home_team'] = team_abbr
                    games_by_id[game_id]['home_score'] = points
                else:
                    games_by_id[game_id]['away_team'] = team_abbr
                    games_by_id[game_id]['away_score'] = points

        self.stdout.write(f"Found {len(games_by_id)} games in CSV")

        # Load games into database
        created = 0
        updated = 0
        skipped = 0

        for game_id, game_data in games_by_id.items():
            # Skip incomplete games
            if not all(k in game_data for k in ['home_team', 'away_team', 'home_score', 'away_score']):
                skipped += 1
                continue

            try:
                game_date = datetime.strptime(game_data['date'], '%Y-%m-%d').date()

                obj, was_created = HistoricalGame.objects.update_or_create(
                    api_game_id=int(game_id),
                    defaults={
                        'date': game_date,
                        'season': game_data['season'],
                        'home_team_abbr': game_data['home_team'],
                        'away_team_abbr': game_data['away_team'],
                        'home_score': game_data['home_score'],
                        'away_score': game_data['away_score'],
                    }
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error loading game {game_id}: {e}"))
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Created: {created}, Updated: {updated}, Skipped: {skipped}"))

        # Calculate pre-game features
        self.stdout.write("\nCalculating pre-game features...")
        self._calculate_features()
        self.stdout.write(self.style.SUCCESS("Done!"))

        self.stdout.write(f"\nTotal games in database: {HistoricalGame.objects.count()}")

    def _calculate_features(self):
        """Calculate pre-game features for all historical games."""
        games = HistoricalGame.objects.order_by('date').all()

        team_stats = defaultdict(lambda: {
            'wins': 0, 'losses': 0,
            'home_wins': 0, 'home_losses': 0,
            'away_wins': 0, 'away_losses': 0,
            'recent_games': [],
            'streak': 0,
            'last_game_date': None,
        })

        h2h_by_season = defaultdict(lambda: defaultdict(lambda: {'home_wins': 0, 'away_wins': 0}))

        processed = 0
        total = games.count()

        for game in games:
            home = game.home_team_abbr
            away = game.away_team_abbr
            season = game.season

            home_stats = team_stats[home]
            away_stats = team_stats[away]

            h2h_key = tuple(sorted([home, away]))
            h2h = h2h_by_season[season][h2h_key]

            # Pre-game features
            home_games = home_stats['wins'] + home_stats['losses']
            away_games = away_stats['wins'] + away_stats['losses']
            game.home_win_pct = Decimal(str(round(home_stats['wins'] / home_games, 3))) if home_games > 0 else None
            game.away_win_pct = Decimal(str(round(away_stats['wins'] / away_games, 3))) if away_games > 0 else None

            home_recent = home_stats['recent_games'][-10:]
            away_recent = away_stats['recent_games'][-10:]

            if home_recent:
                game.home_ppg_l10 = Decimal(str(round(sum(g[0] for g in home_recent) / len(home_recent), 1)))
                game.home_papg_l10 = Decimal(str(round(sum(g[1] for g in home_recent) / len(home_recent), 1)))
            if away_recent:
                game.away_ppg_l10 = Decimal(str(round(sum(g[0] for g in away_recent) / len(away_recent), 1)))
                game.away_papg_l10 = Decimal(str(round(sum(g[1] for g in away_recent) / len(away_recent), 1)))

            game.home_streak = home_stats['streak']
            game.away_streak = away_stats['streak']

            if home_stats['last_game_date']:
                game.home_rest_days = min((game.date - home_stats['last_game_date']).days, 7)
            if away_stats['last_game_date']:
                game.away_rest_days = min((game.date - away_stats['last_game_date']).days, 7)

            if h2h_key[0] == home:
                game.h2h_home_wins = h2h['home_wins']
                game.h2h_away_wins = h2h['away_wins']
            else:
                game.h2h_home_wins = h2h['away_wins']
                game.h2h_away_wins = h2h['home_wins']

            game.home_home_wins = home_stats['home_wins']
            game.home_home_losses = home_stats['home_losses']
            game.away_away_wins = away_stats['away_wins']
            game.away_away_losses = away_stats['away_losses']

            game.save()

            # Update stats after saving pre-game features
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

            home_stats['recent_games'].append((game.home_score, game.away_score))
            away_stats['recent_games'].append((game.away_score, game.home_score))

            if len(home_stats['recent_games']) > 15:
                home_stats['recent_games'] = home_stats['recent_games'][-15:]
            if len(away_stats['recent_games']) > 15:
                away_stats['recent_games'] = away_stats['recent_games'][-15:]

            home_stats['last_game_date'] = game.date
            away_stats['last_game_date'] = game.date

            processed += 1
            if processed % 1000 == 0:
                self.stdout.write(f"  Processed {processed}/{total}...")

        self.stdout.write(f"  Processed {processed}/{total}")
