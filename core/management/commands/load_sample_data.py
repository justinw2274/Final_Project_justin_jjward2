"""
Management command to load sample NBA data.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from core.models import Team, Player, Game


class Command(BaseCommand):
    help = 'Loads sample NBA data (teams, players, games)'

    def handle(self, *args, **options):
        self.stdout.write('Loading sample NBA data...')

        # Create teams
        teams_data = [
            # Eastern Conference
            {'name': 'Celtics', 'city': 'Boston', 'abbreviation': 'BOS', 'conference': 'EAST', 'wins': 25, 'losses': 10},
            {'name': 'Bucks', 'city': 'Milwaukee', 'abbreviation': 'MIL', 'conference': 'EAST', 'wins': 22, 'losses': 12},
            {'name': '76ers', 'city': 'Philadelphia', 'abbreviation': 'PHI', 'conference': 'EAST', 'wins': 20, 'losses': 14},
            {'name': 'Cavaliers', 'city': 'Cleveland', 'abbreviation': 'CLE', 'conference': 'EAST', 'wins': 23, 'losses': 11},
            {'name': 'Knicks', 'city': 'New York', 'abbreviation': 'NYK', 'conference': 'EAST', 'wins': 21, 'losses': 14},
            {'name': 'Heat', 'city': 'Miami', 'abbreviation': 'MIA', 'conference': 'EAST', 'wins': 18, 'losses': 16},
            {'name': 'Hawks', 'city': 'Atlanta', 'abbreviation': 'ATL', 'conference': 'EAST', 'wins': 16, 'losses': 18},
            {'name': 'Bulls', 'city': 'Chicago', 'abbreviation': 'CHI', 'conference': 'EAST', 'wins': 15, 'losses': 19},
            {'name': 'Nets', 'city': 'Brooklyn', 'abbreviation': 'BKN', 'conference': 'EAST', 'wins': 14, 'losses': 20},
            {'name': 'Raptors', 'city': 'Toronto', 'abbreviation': 'TOR', 'conference': 'EAST', 'wins': 13, 'losses': 21},
            {'name': 'Magic', 'city': 'Orlando', 'abbreviation': 'ORL', 'conference': 'EAST', 'wins': 19, 'losses': 16},
            {'name': 'Pacers', 'city': 'Indiana', 'abbreviation': 'IND', 'conference': 'EAST', 'wins': 20, 'losses': 15},
            {'name': 'Pistons', 'city': 'Detroit', 'abbreviation': 'DET', 'conference': 'EAST', 'wins': 8, 'losses': 26},
            {'name': 'Hornets', 'city': 'Charlotte', 'abbreviation': 'CHA', 'conference': 'EAST', 'wins': 10, 'losses': 24},
            {'name': 'Wizards', 'city': 'Washington', 'abbreviation': 'WAS', 'conference': 'EAST', 'wins': 9, 'losses': 25},
            # Western Conference
            {'name': 'Thunder', 'city': 'Oklahoma City', 'abbreviation': 'OKC', 'conference': 'WEST', 'wins': 26, 'losses': 8},
            {'name': 'Nuggets', 'city': 'Denver', 'abbreviation': 'DEN', 'conference': 'WEST', 'wins': 22, 'losses': 12},
            {'name': 'Timberwolves', 'city': 'Minnesota', 'abbreviation': 'MIN', 'conference': 'WEST', 'wins': 21, 'losses': 13},
            {'name': 'Clippers', 'city': 'Los Angeles', 'abbreviation': 'LAC', 'conference': 'WEST', 'wins': 20, 'losses': 14},
            {'name': 'Lakers', 'city': 'Los Angeles', 'abbreviation': 'LAL', 'conference': 'WEST', 'wins': 18, 'losses': 16},
            {'name': 'Suns', 'city': 'Phoenix', 'abbreviation': 'PHX', 'conference': 'WEST', 'wins': 19, 'losses': 15},
            {'name': 'Kings', 'city': 'Sacramento', 'abbreviation': 'SAC', 'conference': 'WEST', 'wins': 17, 'losses': 17},
            {'name': 'Warriors', 'city': 'Golden State', 'abbreviation': 'GSW', 'conference': 'WEST', 'wins': 16, 'losses': 18},
            {'name': 'Mavericks', 'city': 'Dallas', 'abbreviation': 'DAL', 'conference': 'WEST', 'wins': 20, 'losses': 15},
            {'name': 'Rockets', 'city': 'Houston', 'abbreviation': 'HOU', 'conference': 'WEST', 'wins': 18, 'losses': 16},
            {'name': 'Grizzlies', 'city': 'Memphis', 'abbreviation': 'MEM', 'conference': 'WEST', 'wins': 15, 'losses': 19},
            {'name': 'Pelicans', 'city': 'New Orleans', 'abbreviation': 'NOP', 'conference': 'WEST', 'wins': 14, 'losses': 20},
            {'name': 'Spurs', 'city': 'San Antonio', 'abbreviation': 'SAS', 'conference': 'WEST', 'wins': 12, 'losses': 22},
            {'name': 'Jazz', 'city': 'Utah', 'abbreviation': 'UTA', 'conference': 'WEST', 'wins': 11, 'losses': 23},
            {'name': 'Trail Blazers', 'city': 'Portland', 'abbreviation': 'POR', 'conference': 'WEST', 'wins': 10, 'losses': 24},
        ]

        teams = {}
        for team_data in teams_data:
            team, created = Team.objects.update_or_create(
                abbreviation=team_data['abbreviation'],
                defaults=team_data
            )
            teams[team_data['abbreviation']] = team
            if created:
                self.stdout.write(f'  Created team: {team}')

        self.stdout.write(self.style.SUCCESS(f'Loaded {len(teams_data)} teams'))

        # Create sample players
        players_data = [
            # Celtics
            {'name': 'Jayson Tatum', 'team': 'BOS', 'position': 'SF', 'jersey_number': 0, 'avg_points': 27.5, 'avg_rebounds': 8.2, 'avg_assists': 4.8},
            {'name': 'Jaylen Brown', 'team': 'BOS', 'position': 'SG', 'jersey_number': 7, 'avg_points': 23.1, 'avg_rebounds': 5.4, 'avg_assists': 3.5},
            {'name': 'Derrick White', 'team': 'BOS', 'position': 'PG', 'jersey_number': 9, 'avg_points': 15.2, 'avg_rebounds': 4.1, 'avg_assists': 5.2},
            # Bucks
            {'name': 'Giannis Antetokounmpo', 'team': 'MIL', 'position': 'PF', 'jersey_number': 34, 'avg_points': 31.2, 'avg_rebounds': 11.8, 'avg_assists': 5.9},
            {'name': 'Damian Lillard', 'team': 'MIL', 'position': 'PG', 'jersey_number': 0, 'avg_points': 26.5, 'avg_rebounds': 4.4, 'avg_assists': 7.1},
            # Lakers
            {'name': 'LeBron James', 'team': 'LAL', 'position': 'SF', 'jersey_number': 23, 'avg_points': 25.8, 'avg_rebounds': 7.5, 'avg_assists': 8.2},
            {'name': 'Anthony Davis', 'team': 'LAL', 'position': 'PF', 'jersey_number': 3, 'avg_points': 24.6, 'avg_rebounds': 12.3, 'avg_assists': 3.4},
            # Warriors
            {'name': 'Stephen Curry', 'team': 'GSW', 'position': 'PG', 'jersey_number': 30, 'avg_points': 28.3, 'avg_rebounds': 4.5, 'avg_assists': 5.2},
            {'name': 'Klay Thompson', 'team': 'GSW', 'position': 'SG', 'jersey_number': 11, 'avg_points': 17.8, 'avg_rebounds': 3.2, 'avg_assists': 2.1},
            # Thunder
            {'name': 'Shai Gilgeous-Alexander', 'team': 'OKC', 'position': 'PG', 'jersey_number': 2, 'avg_points': 31.5, 'avg_rebounds': 5.4, 'avg_assists': 6.2},
            {'name': 'Chet Holmgren', 'team': 'OKC', 'position': 'C', 'jersey_number': 7, 'avg_points': 16.8, 'avg_rebounds': 7.9, 'avg_assists': 2.5},
            # Nuggets
            {'name': 'Nikola Jokic', 'team': 'DEN', 'position': 'C', 'jersey_number': 15, 'avg_points': 26.4, 'avg_rebounds': 12.2, 'avg_assists': 9.1},
            {'name': 'Jamal Murray', 'team': 'DEN', 'position': 'PG', 'jersey_number': 27, 'avg_points': 21.3, 'avg_rebounds': 4.1, 'avg_assists': 6.5},
        ]

        player_count = 0
        for player_data in players_data:
            team = teams.get(player_data['team'])
            if team:
                Player.objects.update_or_create(
                    name=player_data['name'],
                    team=team,
                    defaults={
                        'position': player_data['position'],
                        'jersey_number': player_data['jersey_number'],
                        'avg_points': Decimal(str(player_data['avg_points'])),
                        'avg_rebounds': Decimal(str(player_data['avg_rebounds'])),
                        'avg_assists': Decimal(str(player_data['avg_assists'])),
                    }
                )
                player_count += 1

        self.stdout.write(self.style.SUCCESS(f'Loaded {player_count} players'))

        # Create sample games
        today = timezone.now().date()
        team_list = list(teams.values())

        # Past games (completed)
        for i in range(10):
            game_date = today - timedelta(days=i+1)
            home_team = random.choice(team_list)
            away_team = random.choice([t for t in team_list if t != home_team])

            home_score = random.randint(95, 130)
            away_score = random.randint(95, 130)

            home_win_prob = Decimal(str(round(random.uniform(35, 75), 2)))
            confidence = Decimal(str(round(random.uniform(45, 80), 2)))
            spread = Decimal(str(round(random.uniform(-10, 10), 1)))

            Game.objects.update_or_create(
                date=game_date,
                home_team=home_team,
                away_team=away_team,
                defaults={
                    'home_score': home_score,
                    'away_score': away_score,
                    'status': 'final',
                    'prediction_home_win_prob': home_win_prob,
                    'prediction_confidence': confidence,
                    'predicted_spread': spread,
                }
            )

        # Today's games
        for i in range(3):
            home_team = team_list[i*2]
            away_team = team_list[i*2 + 1]

            home_win_prob = Decimal(str(round(random.uniform(35, 75), 2)))
            confidence = Decimal(str(round(random.uniform(45, 80), 2)))
            spread = Decimal(str(round(random.uniform(-10, 10), 1)))

            game, _ = Game.objects.update_or_create(
                date=today,
                home_team=home_team,
                away_team=away_team,
                defaults={
                    'status': 'scheduled',
                    'prediction_home_win_prob': home_win_prob,
                    'prediction_confidence': confidence,
                    'predicted_spread': spread,
                    'is_featured': i == 0,
                }
            )

        # Upcoming games
        for i in range(7):
            game_date = today + timedelta(days=i+1)
            games_per_day = random.randint(2, 5)

            for j in range(games_per_day):
                home_team = random.choice(team_list)
                away_team = random.choice([t for t in team_list if t != home_team])

                home_win_prob = Decimal(str(round(random.uniform(35, 75), 2)))
                confidence = Decimal(str(round(random.uniform(45, 80), 2)))
                spread = Decimal(str(round(random.uniform(-10, 10), 1)))

                Game.objects.update_or_create(
                    date=game_date,
                    home_team=home_team,
                    away_team=away_team,
                    defaults={
                        'status': 'scheduled',
                        'prediction_home_win_prob': home_win_prob,
                        'prediction_confidence': confidence,
                        'predicted_spread': spread,
                    }
                )

        game_count = Game.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Loaded {game_count} games'))

        self.stdout.write(self.style.SUCCESS('Sample data loaded successfully!'))
