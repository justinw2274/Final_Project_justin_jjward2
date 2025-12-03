"""
Management command to load comprehensive NBA data from the API.
Calculates all advanced features for ML predictions.

Features calculated:
- Team records and Elo ratings
- Four Factors estimates
- Win/loss streaks
- Schedule features (B2B, 3-in-4, rest days)
- Head-to-head records
- Strength of schedule
- Rolling performance trends

Data Leakage Prevention:
- Games processed in chronological order
- Only pre-game data used for predictions
- Snapshots stored for historical accuracy
"""
from django.core.management.base import BaseCommand
from datetime import timedelta, date
from decimal import Decimal
from collections import defaultdict
import time

from core.models import Team, Player, Game, HeadToHead
from core.services.nba_api import NBAApiService
from core.services.prediction_model import predict_game, NBAPredictor


# Key players for each team (2025-26 season rosters)
KEY_PLAYERS = {
    'BOS': [('Jayson Tatum', 'SF', 0, 27.0, 8.5, 5.2), ('Jaylen Brown', 'SG', 7, 24.5, 5.8, 4.1), ('Derrick White', 'PG', 9, 16.2, 4.5, 5.5)],
    'CLE': [('Donovan Mitchell', 'SG', 45, 24.2, 4.5, 4.8), ('Darius Garland', 'PG', 10, 21.5, 2.8, 6.8), ('Evan Mobley', 'PF', 4, 18.5, 9.2, 3.2)],
    'OKC': [('Shai Gilgeous-Alexander', 'PG', 2, 31.5, 5.5, 6.2), ('Jalen Williams', 'SF', 8, 20.8, 5.2, 5.5), ('Chet Holmgren', 'C', 7, 16.5, 8.5, 2.8)],
    'HOU': [('Jalen Green', 'SG', 4, 19.8, 5.2, 3.5), ('Alperen Sengun', 'C', 28, 18.5, 10.2, 5.0), ('Fred VanVleet', 'PG', 5, 15.8, 4.2, 6.5)],
    'DAL': [('Luka Doncic', 'PG', 77, 28.5, 8.2, 8.5), ('Kyrie Irving', 'SG', 11, 24.2, 5.0, 5.2), ('Klay Thompson', 'SG', 31, 14.2, 3.5, 2.2)],
    'MEM': [('Ja Morant', 'PG', 12, 21.5, 4.5, 8.2), ('Desmond Bane', 'SG', 22, 18.5, 4.8, 4.5), ('Jaren Jackson Jr', 'PF', 13, 22.2, 6.2, 2.0)],
    'DEN': [('Nikola Jokic', 'C', 15, 29.5, 13.2, 10.5), ('Jamal Murray', 'PG', 27, 21.0, 4.2, 6.5), ('Michael Porter Jr', 'SF', 1, 18.5, 7.2, 1.5)],
    'LAC': [('James Harden', 'PG', 1, 21.5, 7.5, 9.2), ('Kawhi Leonard', 'SF', 2, 23.8, 6.2, 3.5), ('Norman Powell', 'SG', 24, 18.2, 3.2, 2.2)],
    'MIN': [('Anthony Edwards', 'SG', 5, 27.5, 5.8, 4.2), ('Julius Randle', 'PF', 30, 20.2, 9.5, 4.5), ('Rudy Gobert', 'C', 27, 11.2, 12.5, 1.8)],
    'MIA': [('Jimmy Butler', 'SF', 22, 18.5, 5.5, 4.8), ('Tyler Herro', 'SG', 14, 23.5, 5.2, 4.8), ('Bam Adebayo', 'C', 13, 16.2, 10.5, 5.2)],
    'NYK': [('Jalen Brunson', 'PG', 11, 25.2, 3.5, 7.5), ('Karl-Anthony Towns', 'C', 32, 25.5, 13.8, 3.2), ('OG Anunoby', 'SF', 8, 16.2, 4.8, 2.2)],
    'LAL': [('LeBron James', 'SF', 23, 23.5, 7.8, 9.2), ('Anthony Davis', 'PF', 3, 25.2, 11.5, 3.5), ('Austin Reaves', 'SG', 15, 17.2, 4.2, 5.5)],
    'GSW': [('Stephen Curry', 'PG', 30, 22.5, 5.2, 6.5), ('Andrew Wiggins', 'SF', 22, 17.2, 4.5, 2.5), ('Draymond Green', 'PF', 23, 9.2, 6.5, 6.2)],
    'IND': [('Tyrese Haliburton', 'PG', 0, 18.2, 4.0, 8.8), ('Pascal Siakam', 'PF', 43, 20.5, 7.5, 3.8), ('Myles Turner', 'C', 33, 15.8, 7.2, 1.5)],
    'PHX': [('Kevin Durant', 'SF', 35, 27.2, 6.5, 4.2), ('Devin Booker', 'SG', 1, 25.5, 4.2, 6.8), ('Bradley Beal', 'SG', 3, 18.2, 4.5, 3.5)],
    'ORL': [('Paolo Banchero', 'PF', 5, 22.5, 7.5, 5.5), ('Franz Wagner', 'SF', 22, 21.2, 5.8, 5.2), ('Jalen Suggs', 'PG', 4, 14.5, 3.5, 4.2)],
    'SAC': [('De\'Aaron Fox', 'PG', 5, 26.2, 4.8, 6.2), ('Domantas Sabonis', 'C', 10, 19.5, 13.2, 6.5), ('Keegan Murray', 'SF', 13, 15.2, 5.5, 2.2)],
    'ATL': [('Trae Young', 'PG', 11, 22.5, 3.2, 11.5), ('Jalen Johnson', 'SF', 1, 19.2, 9.5, 4.8), ('De\'Andre Hunter', 'SF', 12, 14.5, 4.2, 2.2)],
    'MIL': [('Giannis Antetokounmpo', 'PF', 34, 32.5, 12.2, 6.2), ('Damian Lillard', 'PG', 0, 25.8, 4.5, 7.5), ('Brook Lopez', 'C', 11, 12.5, 5.2, 1.8)],
    'SAS': [('Victor Wembanyama', 'C', 1, 22.2, 10.5, 3.8), ('Devin Vassell', 'SG', 24, 18.5, 4.2, 4.5), ('Jeremy Sochan', 'PF', 10, 15.2, 8.2, 3.5)],
    'DET': [('Cade Cunningham', 'PG', 2, 24.5, 7.2, 9.2), ('Jaden Ivey', 'SG', 23, 17.2, 4.5, 4.8), ('Tobias Harris', 'PF', 12, 13.5, 6.5, 2.5)],
    'CHI': [('Zach LaVine', 'SG', 8, 22.2, 4.5, 4.2), ('Coby White', 'PG', 0, 18.5, 4.2, 5.5), ('Nikola Vucevic', 'C', 9, 17.5, 10.2, 3.2)],
    'BKN': [('Cam Thomas', 'SG', 24, 24.5, 3.5, 4.2), ('Cameron Johnson', 'SF', 2, 18.2, 4.5, 3.2), ('Nic Claxton', 'C', 33, 11.2, 8.5, 2.5)],
    'POR': [('Anfernee Simons', 'SG', 1, 22.5, 3.2, 4.8), ('Deandre Ayton', 'C', 2, 17.5, 10.2, 2.2), ('Jerami Grant', 'SF', 9, 18.5, 4.5, 2.5)],
    'TOR': [('Scottie Barnes', 'SF', 4, 20.2, 8.2, 6.5), ('RJ Barrett', 'SF', 9, 21.5, 6.5, 4.5), ('Immanuel Quickley', 'PG', 5, 16.2, 4.5, 6.2)],
    'PHI': [('Tyrese Maxey', 'PG', 0, 26.5, 3.8, 6.2), ('Joel Embiid', 'C', 21, 25.2, 11.2, 3.5), ('Paul George', 'SF', 8, 15.5, 5.5, 4.5)],
    'CHA': [('LaMelo Ball', 'PG', 1, 22.2, 5.5, 8.2), ('Brandon Miller', 'SF', 24, 17.2, 4.8, 2.5), ('Miles Bridges', 'PF', 0, 16.5, 7.2, 2.8)],
    'NOP': [('Zion Williamson', 'PF', 1, 22.5, 8.2, 5.2), ('CJ McCollum', 'SG', 3, 18.5, 4.2, 5.5), ('Brandon Ingram', 'SF', 14, 23.2, 5.5, 5.2)],
    'UTA': [('Lauri Markkanen', 'PF', 23, 21.5, 8.2, 2.5), ('Collin Sexton', 'SG', 2, 17.2, 2.5, 4.2), ('John Collins', 'PF', 20, 15.5, 8.5, 2.2)],
    'WAS': [('Jordan Poole', 'SG', 13, 18.5, 3.2, 4.8), ('Kyle Kuzma', 'PF', 33, 16.2, 5.5, 2.5), ('Malcolm Brogdon', 'PG', 7, 12.5, 4.2, 5.2)],
}


class TeamTracker:
    """Track team statistics as games are processed chronologically."""

    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.points_scored = 0
        self.points_allowed = 0
        self.home_wins = 0
        self.home_losses = 0
        self.away_wins = 0
        self.away_losses = 0
        self.current_streak = 0  # Positive = wins, negative = losses
        self.home_streak = 0
        self.away_streak = 0
        self.last_10_results = []
        self.last_game_date = None
        self.game_dates = []  # For B2B/3in4 calculation
        self.opponents = []  # For SOS calculation
        self.opponent_elos = []
        self.recent_scores = []  # For trend calculation
        self.recent_allowed = []
        self.vs_above_500_wins = 0
        self.vs_above_500_losses = 0
        self.vs_below_500_wins = 0
        self.vs_below_500_losses = 0
        self.elo = 1500.0

    @property
    def games_played(self):
        return self.wins + self.losses

    @property
    def win_pct(self):
        if self.games_played == 0:
            return 0.5
        return self.wins / self.games_played

    def is_b2b(self, game_date):
        """Check if this is a back-to-back game."""
        if not self.last_game_date:
            return False
        return (game_date - self.last_game_date).days == 1

    def is_3in4(self, game_date):
        """Check if this is 3rd game in 4 nights."""
        if len(self.game_dates) < 2:
            return False
        four_days_ago = game_date - timedelta(days=3)
        recent_games = [d for d in self.game_dates if d >= four_days_ago]
        return len(recent_games) >= 2

    def rest_days(self, game_date):
        """Days since last game."""
        if not self.last_game_date:
            return 3
        return max(1, (game_date - self.last_game_date).days)

    def update_after_game(self, game_date, points_for, points_against, is_home, won, opponent_win_pct, opponent_elo):
        """Update all tracking stats after a game."""
        # Basic record
        if won:
            self.wins += 1
            if is_home:
                self.home_wins += 1
            else:
                self.away_wins += 1
        else:
            self.losses += 1
            if is_home:
                self.home_losses += 1
            else:
                self.away_losses += 1

        # Points
        self.points_scored += points_for
        self.points_allowed += points_against

        # Streak tracking
        if won:
            if self.current_streak > 0:
                self.current_streak += 1
            else:
                self.current_streak = 1
            if is_home:
                self.home_streak = self.home_streak + 1 if self.home_streak > 0 else 1
            else:
                self.away_streak = self.away_streak + 1 if self.away_streak > 0 else 1
        else:
            if self.current_streak < 0:
                self.current_streak -= 1
            else:
                self.current_streak = -1
            if is_home:
                self.home_streak = self.home_streak - 1 if self.home_streak < 0 else -1
            else:
                self.away_streak = self.away_streak - 1 if self.away_streak < 0 else -1

        # Last 10
        self.last_10_results.append(1 if won else 0)
        if len(self.last_10_results) > 10:
            self.last_10_results.pop(0)

        # Recent scores for trend
        self.recent_scores.append(points_for)
        self.recent_allowed.append(points_against)
        if len(self.recent_scores) > 10:
            self.recent_scores.pop(0)
            self.recent_allowed.pop(0)

        # Game dates
        self.last_game_date = game_date
        self.game_dates.append(game_date)
        if len(self.game_dates) > 7:
            self.game_dates.pop(0)

        # SOS tracking
        self.opponents.append(opponent_win_pct)
        self.opponent_elos.append(opponent_elo)

        # Record vs above/below .500
        if opponent_win_pct >= 0.5:
            if won:
                self.vs_above_500_wins += 1
            else:
                self.vs_above_500_losses += 1
        else:
            if won:
                self.vs_below_500_wins += 1
            else:
                self.vs_below_500_losses += 1

    @property
    def strength_of_schedule(self):
        if not self.opponents:
            return 0.5
        return sum(self.opponents) / len(self.opponents)

    @property
    def avg_opponent_elo(self):
        if not self.opponent_elos:
            return 1500.0
        return sum(self.opponent_elos) / len(self.opponent_elos)

    @property
    def points_trend(self):
        """Calculate scoring trend (positive = improving)."""
        if len(self.recent_scores) < 5:
            return 0.0
        first_half = self.recent_scores[:len(self.recent_scores)//2]
        second_half = self.recent_scores[len(self.recent_scores)//2:]
        return (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))

    @property
    def defense_trend(self):
        """Calculate defensive trend (negative = improving defense)."""
        if len(self.recent_allowed) < 5:
            return 0.0
        first_half = self.recent_allowed[:len(self.recent_allowed)//2]
        second_half = self.recent_allowed[len(self.recent_allowed)//2:]
        return (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))


class Command(BaseCommand):
    help = 'Loads comprehensive NBA data with all ML features'

    def add_arguments(self, parser):
        parser.add_argument('--api-key', type=str, help='API key for balldontlie.io')
        parser.add_argument('--days-ahead', type=int, default=7, help='Days of future games')

    def handle(self, *args, **options):
        api_key = options.get('api_key')
        days_ahead = options.get('days_ahead')

        self.stdout.write(self.style.NOTICE('Loading comprehensive 2025-26 NBA data...'))

        # Step 1: Load teams
        self.stdout.write('Step 1: Syncing NBA teams...')
        self.load_teams(api_key)

        # Step 2: Fetch all games from API
        self.stdout.write('Step 2: Fetching season games from API...')
        all_games = self.fetch_all_games(api_key, days_ahead)

        # Step 3: Process games chronologically to build features
        self.stdout.write('Step 3: Processing games chronologically (avoiding data leakage)...')
        self.process_games_chronologically(all_games)

        # Step 4: Load players
        self.stdout.write('Step 4: Loading key players...')
        self.load_players()

        # Step 5: Set featured game
        self.stdout.write('Step 5: Setting featured game...')
        self.set_featured_game()

        self.stdout.write(self.style.SUCCESS('Data loaded successfully!'))
        self.print_summary()

    def load_teams(self, api_key):
        service = NBAApiService(api_key)
        api_teams = service.get_teams()
        conference_map = {'East': 'EAST', 'West': 'WEST'}

        for api_team in api_teams:
            Team.objects.update_or_create(
                abbreviation=api_team.get('abbreviation'),
                defaults={
                    'name': api_team.get('name'),
                    'city': api_team.get('city'),
                    'conference': conference_map.get(api_team.get('conference'), 'EAST'),
                }
            )
        self.stdout.write(f'  Synced {len(api_teams)} teams')

    def fetch_all_games(self, api_key, days_ahead):
        service = NBAApiService(api_key)
        today = date.today()
        season_start = date(2025, 10, 22)
        end_date = today + timedelta(days=days_ahead)

        all_games = []
        cursor = None
        self.stdout.write(f'  Fetching {season_start} to {end_date}...')

        while True:
            games, cursor = service.get_games(season_start, end_date, cursor=cursor)
            all_games.extend(games)
            if not cursor:
                break
            time.sleep(0.3)

        self.stdout.write(f'  Found {len(all_games)} games')
        return all_games

    def process_games_chronologically(self, all_games):
        """Process games in date order to calculate features without data leakage."""
        # Initialize trackers for each team
        trackers = {}
        for team in Team.objects.all():
            trackers[team.abbreviation] = TeamTracker()

        # H2H tracking
        h2h_records = defaultdict(lambda: {'home_wins': 0, 'away_wins': 0})

        # Sort games by date
        sorted_games = sorted(all_games, key=lambda x: x['date'])
        completed = [g for g in sorted_games if g.get('status') == 'Final']
        scheduled = [g for g in sorted_games if g.get('status') != 'Final']

        self.stdout.write(f'  Processing {len(completed)} completed games...')

        # Process completed games first
        for api_game in completed:
            home_abbrev = api_game['home_team']['abbreviation']
            away_abbrev = api_game['visitor_team']['abbreviation']
            game_date = date.fromisoformat(api_game['date'][:10])
            home_score = api_game.get('home_team_score', 0)
            away_score = api_game.get('visitor_team_score', 0)

            if home_abbrev not in trackers or away_abbrev not in trackers:
                continue

            home_tracker = trackers[home_abbrev]
            away_tracker = trackers[away_abbrev]

            # Save pre-game state for prediction
            pre_game_state = {
                'home_elo': home_tracker.elo,
                'away_elo': away_tracker.elo,
                'home_streak': home_tracker.current_streak,
                'away_streak': away_tracker.current_streak,
                'home_rest': home_tracker.rest_days(game_date),
                'away_rest': away_tracker.rest_days(game_date),
                'home_b2b': home_tracker.is_b2b(game_date),
                'away_b2b': away_tracker.is_b2b(game_date),
                'home_3in4': home_tracker.is_3in4(game_date),
                'away_3in4': away_tracker.is_3in4(game_date),
            }

            # H2H key (alphabetical order)
            h2h_key = tuple(sorted([home_abbrev, away_abbrev]))
            h2h = h2h_records[h2h_key]

            # Determine winner
            home_won = home_score > away_score

            # Update trackers (post-game)
            home_tracker.update_after_game(
                game_date, home_score, away_score, True, home_won,
                away_tracker.win_pct, away_tracker.elo
            )
            away_tracker.update_after_game(
                game_date, away_score, home_score, False, not home_won,
                home_tracker.win_pct, home_tracker.elo
            )

            # Update Elo
            margin = abs(home_score - away_score)
            predictor = NBAPredictor()
            if home_won:
                elo_change = self._update_elo(home_tracker, away_tracker, True, margin)
            else:
                elo_change = self._update_elo(away_tracker, home_tracker, False, margin)

            # Update H2H
            if home_won:
                if home_abbrev == h2h_key[0]:
                    h2h['home_wins'] += 1
                else:
                    h2h['away_wins'] += 1
            else:
                if away_abbrev == h2h_key[0]:
                    h2h['home_wins'] += 1
                else:
                    h2h['away_wins'] += 1

            # Save game to database with pre-game features
            try:
                home_team = Team.objects.get(abbreviation=home_abbrev)
                away_team = Team.objects.get(abbreviation=away_abbrev)

                Game.objects.update_or_create(
                    date=game_date,
                    home_team=home_team,
                    away_team=away_team,
                    defaults={
                        'home_score': home_score,
                        'away_score': away_score,
                        'status': 'final',
                        'home_rest_days': pre_game_state['home_rest'],
                        'away_rest_days': pre_game_state['away_rest'],
                        'home_b2b': pre_game_state['home_b2b'],
                        'away_b2b': pre_game_state['away_b2b'],
                        'home_3in4': pre_game_state['home_3in4'],
                        'away_3in4': pre_game_state['away_3in4'],
                        'home_elo_pre': Decimal(str(round(pre_game_state['home_elo'], 1))),
                        'away_elo_pre': Decimal(str(round(pre_game_state['away_elo'], 1))),
                        'home_streak_pre': pre_game_state['home_streak'],
                        'away_streak_pre': pre_game_state['away_streak'],
                        'h2h_home_wins': h2h['home_wins'] if home_abbrev == h2h_key[0] else h2h['away_wins'],
                        'h2h_away_wins': h2h['away_wins'] if home_abbrev == h2h_key[0] else h2h['home_wins'],
                    }
                )
            except Team.DoesNotExist:
                continue

        # Update team models with final stats
        self.stdout.write('  Updating team statistics...')
        for abbrev, tracker in trackers.items():
            try:
                team = Team.objects.get(abbreviation=abbrev)
                self._update_team_from_tracker(team, tracker)
            except Team.DoesNotExist:
                continue

        # Process scheduled games with predictions
        self.stdout.write(f'  Processing {len(scheduled)} scheduled games with predictions...')
        for api_game in scheduled:
            home_abbrev = api_game['home_team']['abbreviation']
            away_abbrev = api_game['visitor_team']['abbreviation']
            game_date = date.fromisoformat(api_game['date'][:10])

            try:
                home_team = Team.objects.get(abbreviation=home_abbrev)
                away_team = Team.objects.get(abbreviation=away_abbrev)
                home_tracker = trackers.get(home_abbrev)
                away_tracker = trackers.get(away_abbrev)

                if not home_tracker or not away_tracker:
                    continue

                # Calculate schedule features
                h2h_key = tuple(sorted([home_abbrev, away_abbrev]))
                h2h = h2h_records[h2h_key]

                # Create game with schedule features
                game, _ = Game.objects.update_or_create(
                    date=game_date,
                    home_team=home_team,
                    away_team=away_team,
                    defaults={
                        'status': 'scheduled',
                        'home_rest_days': home_tracker.rest_days(game_date),
                        'away_rest_days': away_tracker.rest_days(game_date),
                        'home_b2b': home_tracker.is_b2b(game_date),
                        'away_b2b': away_tracker.is_b2b(game_date),
                        'home_3in4': home_tracker.is_3in4(game_date),
                        'away_3in4': away_tracker.is_3in4(game_date),
                        'home_elo_pre': team.elo_rating,
                        'away_elo_pre': away_team.elo_rating,
                        'home_streak_pre': home_tracker.current_streak,
                        'away_streak_pre': away_tracker.current_streak,
                        'h2h_home_wins': h2h['home_wins'] if home_abbrev == h2h_key[0] else h2h['away_wins'],
                        'h2h_away_wins': h2h['away_wins'] if home_abbrev == h2h_key[0] else h2h['home_wins'],
                    }
                )

                # Generate prediction
                home_prob, confidence, spread = predict_game(home_team, away_team, game_date, game)
                game.prediction_home_win_prob = home_prob
                game.prediction_confidence = confidence
                game.predicted_spread = spread
                game.save()

            except Team.DoesNotExist:
                continue

    def _update_elo(self, winner_tracker, loser_tracker, winner_is_home, margin):
        """Update Elo ratings after a game."""
        K = 20
        home_advantage = 100

        if winner_is_home:
            winner_elo = winner_tracker.elo + home_advantage
            loser_elo = loser_tracker.elo
        else:
            winner_elo = winner_tracker.elo
            loser_elo = loser_tracker.elo + home_advantage

        expected = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        mov_mult = min(2.5, max(1.0, (margin + 3) ** 0.8 / 20))
        elo_change = K * mov_mult * (1 - expected)

        winner_tracker.elo += elo_change
        loser_tracker.elo -= elo_change

        return elo_change

    def _update_team_from_tracker(self, team, tracker):
        """Update Team model from tracker data."""
        team.wins = tracker.wins
        team.losses = tracker.losses
        team.elo_rating = Decimal(str(round(tracker.elo, 1)))
        team.current_streak = tracker.current_streak
        team.home_streak = tracker.home_streak
        team.away_streak = tracker.away_streak
        team.last_10_wins = sum(tracker.last_10_results)
        team.last_10_losses = len(tracker.last_10_results) - sum(tracker.last_10_results)
        team.last_game_date = tracker.last_game_date
        team.record_vs_above_500_wins = tracker.vs_above_500_wins
        team.record_vs_above_500_losses = tracker.vs_above_500_losses
        team.record_vs_below_500_wins = tracker.vs_below_500_wins
        team.record_vs_below_500_losses = tracker.vs_below_500_losses
        team.strength_of_schedule = Decimal(str(round(tracker.strength_of_schedule, 3)))
        team.avg_opponent_elo = Decimal(str(round(tracker.avg_opponent_elo, 1)))
        team.points_trend = Decimal(str(round(tracker.points_trend, 2)))
        team.defense_trend = Decimal(str(round(tracker.defense_trend, 2)))

        # Calculate averages
        if tracker.games_played > 0:
            avg_scored = tracker.points_scored / tracker.games_played
            avg_allowed = tracker.points_allowed / tracker.games_played
            team.avg_points_scored = Decimal(str(round(avg_scored, 1)))
            team.avg_points_allowed = Decimal(str(round(avg_allowed, 1)))
            team.offensive_rating = Decimal(str(round(avg_scored, 1)))
            team.defensive_rating = Decimal(str(round(avg_allowed, 1)))

            # Estimate Four Factors
            eff = avg_scored / 110
            team.efg_pct = Decimal(str(round(0.50 + (eff - 1) * 0.08, 3)))
            team.tov_pct = Decimal(str(round(0.13 - (eff - 1) * 0.02, 3)))
            team.orb_pct = Decimal(str(round(0.25 + (eff - 1) * 0.03, 3)))
            team.ft_rate = Decimal(str(round(0.25 + (eff - 1) * 0.02, 3)))

            def_eff = 110 / avg_allowed
            team.opp_efg_pct = Decimal(str(round(0.54 - (def_eff - 1) * 0.08, 3)))
            team.opp_tov_pct = Decimal(str(round(0.13 + (def_eff - 1) * 0.02, 3)))
            team.opp_orb_pct = Decimal(str(round(0.25 - (def_eff - 1) * 0.03, 3)))
            team.opp_ft_rate = Decimal(str(round(0.25 - (def_eff - 1) * 0.02, 3)))

            team.pace = Decimal(str(round(98 + (avg_scored + avg_allowed - 220) * 0.5, 1)))

        team.save()

    def load_players(self):
        created = 0
        for abbrev, players in KEY_PLAYERS.items():
            try:
                team = Team.objects.get(abbreviation=abbrev)
                for name, position, jersey, pts, reb, ast in players:
                    _, was_created = Player.objects.update_or_create(
                        name=name, team=team,
                        defaults={
                            'position': position,
                            'jersey_number': jersey,
                            'avg_points': Decimal(str(pts)),
                            'avg_rebounds': Decimal(str(reb)),
                            'avg_assists': Decimal(str(ast)),
                        }
                    )
                    if was_created:
                        created += 1
            except Team.DoesNotExist:
                continue
        self.stdout.write(f'  Loaded {sum(len(p) for p in KEY_PLAYERS.values())} players ({created} new)')

    def set_featured_game(self):
        today = date.today()
        Game.objects.filter(is_featured=True).update(is_featured=False)

        todays_games = Game.objects.filter(date=today, status='scheduled')
        if todays_games.exists():
            best = max(todays_games, key=lambda g: float(g.home_team.elo_rating) + float(g.away_team.elo_rating))
            best.is_featured = True
            best.save()
            self.stdout.write(f'  Featured: {best}')

    def print_summary(self):
        self.stdout.write('\n' + '='*60)
        self.stdout.write('COMPREHENSIVE DATA SUMMARY')
        self.stdout.write('='*60)
        self.stdout.write(f'Teams: {Team.objects.count()}')
        self.stdout.write(f'Players: {Player.objects.count()}')
        self.stdout.write(f'Games: {Game.objects.count()}')
        self.stdout.write(f'  - Completed: {Game.objects.filter(status="final").count()}')
        self.stdout.write(f'  - Scheduled: {Game.objects.filter(status="scheduled").count()}')

        self.stdout.write('\nTop 5 Teams by Elo:')
        for i, t in enumerate(Team.objects.order_by('-elo_rating')[:5], 1):
            self.stdout.write(f'  {i}. {t.abbreviation}: {t.elo_rating} ({t.record}) Streak: {t.current_streak:+d}')

        self.stdout.write('\nFeatures calculated:')
        self.stdout.write('  - Win/Loss streaks')
        self.stdout.write('  - Back-to-back detection')
        self.stdout.write('  - 3-in-4 nights detection')
        self.stdout.write('  - Rest days')
        self.stdout.write('  - Strength of schedule')
        self.stdout.write('  - Performance trends')
        self.stdout.write('  - H2H records')
        self.stdout.write('  - Pre-game Elo snapshots')
