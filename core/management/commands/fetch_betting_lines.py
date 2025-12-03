"""
Management command to fetch betting lines from The Odds API.
Free tier: 500 requests/month

Get your free API key at: https://the-odds-api.com/
Set ODDS_API_KEY environment variable or pass --api-key argument.
"""
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from core.models import Game, Team


class Command(BaseCommand):
    help = 'Fetch betting lines from The Odds API'

    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT = "basketball_nba"

    # Team name mapping (API name -> our abbreviation)
    TEAM_MAP = {
        'Atlanta Hawks': 'ATL',
        'Boston Celtics': 'BOS',
        'Brooklyn Nets': 'BKN',
        'Charlotte Hornets': 'CHA',
        'Chicago Bulls': 'CHI',
        'Cleveland Cavaliers': 'CLE',
        'Dallas Mavericks': 'DAL',
        'Denver Nuggets': 'DEN',
        'Detroit Pistons': 'DET',
        'Golden State Warriors': 'GSW',
        'Houston Rockets': 'HOU',
        'Indiana Pacers': 'IND',
        'Los Angeles Clippers': 'LAC',
        'Los Angeles Lakers': 'LAL',
        'Memphis Grizzlies': 'MEM',
        'Miami Heat': 'MIA',
        'Milwaukee Bucks': 'MIL',
        'Minnesota Timberwolves': 'MIN',
        'New Orleans Pelicans': 'NOP',
        'New York Knicks': 'NYK',
        'Oklahoma City Thunder': 'OKC',
        'Orlando Magic': 'ORL',
        'Philadelphia 76ers': 'PHI',
        'Phoenix Suns': 'PHX',
        'Portland Trail Blazers': 'POR',
        'Sacramento Kings': 'SAC',
        'San Antonio Spurs': 'SAS',
        'Toronto Raptors': 'TOR',
        'Utah Jazz': 'UTA',
        'Washington Wizards': 'WAS',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            required=False,
            help='API key for The Odds API (or set ODDS_API_KEY env var)',
        )
        parser.add_argument(
            '--bookmaker',
            type=str,
            default='fanduel',
            help='Bookmaker to use (default: fanduel)',
        )

    def handle(self, *args, **options):
        # Get API key from argument or settings
        api_key = options.get('api_key') or getattr(settings, 'ODDS_API_KEY', '')

        if not api_key:
            self.stdout.write(self.style.ERROR(
                'No API key provided. Set ODDS_API_KEY environment variable or pass --api-key'
            ))
            return

        bookmaker = options['bookmaker']

        self.stdout.write(f"Fetching NBA betting lines from {bookmaker}...")

        # Fetch odds from API
        params = {
            'apiKey': api_key,
            'regions': 'us',
            'markets': 'spreads,totals,h2h',
            'bookmakers': bookmaker,
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/sports/{self.SPORT}/odds",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"API error: {e}"))
            return

        # Check remaining requests
        remaining = response.headers.get('x-requests-remaining', 'unknown')
        self.stdout.write(f"API requests remaining this month: {remaining}")

        if not data:
            self.stdout.write("No games found")
            return

        updated = 0
        for event in data:
            try:
                home_team_name = event.get('home_team')
                away_team_name = event.get('away_team')

                home_abbr = self.TEAM_MAP.get(home_team_name)
                away_abbr = self.TEAM_MAP.get(away_team_name)

                if not home_abbr or not away_abbr:
                    self.stdout.write(f"  Unknown team: {home_team_name} or {away_team_name}")
                    continue

                # Parse game date
                commence_time = event.get('commence_time')
                if commence_time:
                    game_date = datetime.fromisoformat(commence_time.replace('Z', '+00:00')).date()
                else:
                    continue

                # Find matching game in our database
                game = Game.objects.filter(
                    home_team__abbreviation=home_abbr,
                    away_team__abbreviation=away_abbr,
                    date=game_date
                ).first()

                if not game:
                    # Try date +/- 1 day due to timezone differences
                    game = Game.objects.filter(
                        home_team__abbreviation=home_abbr,
                        away_team__abbreviation=away_abbr,
                        date__gte=game_date - timedelta(days=1),
                        date__lte=game_date + timedelta(days=1)
                    ).first()

                if not game:
                    self.stdout.write(f"  Game not found: {away_abbr} @ {home_abbr} on {game_date}")
                    continue

                # Extract odds from bookmaker
                bookmakers = event.get('bookmakers', [])
                if not bookmakers:
                    continue

                bm = bookmakers[0]  # First bookmaker
                markets = {m['key']: m for m in bm.get('markets', [])}

                # Get spread
                if 'spreads' in markets:
                    for outcome in markets['spreads'].get('outcomes', []):
                        if outcome['name'] == home_team_name:
                            game.vegas_spread = Decimal(str(outcome.get('point', 0)))

                # Get total
                if 'totals' in markets:
                    for outcome in markets['totals'].get('outcomes', []):
                        if outcome['name'] == 'Over':
                            game.vegas_total = Decimal(str(outcome.get('point', 0)))

                # Get moneylines
                if 'h2h' in markets:
                    for outcome in markets['h2h'].get('outcomes', []):
                        if outcome['name'] == home_team_name:
                            game.vegas_home_ml = outcome.get('price')
                        elif outcome['name'] == away_team_name:
                            game.vegas_away_ml = outcome.get('price')

                game.save()
                updated += 1
                self.stdout.write(
                    f"  Updated: {away_abbr} @ {home_abbr} - "
                    f"Spread: {game.vegas_spread}, Total: {game.vegas_total}"
                )

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Error processing event: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nUpdated {updated} games with betting lines"))
