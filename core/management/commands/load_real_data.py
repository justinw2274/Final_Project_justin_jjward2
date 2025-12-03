"""
Management command to load real NBA data from the API.
Fetches teams, standings, games, and calculates advanced statistics.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import time

from core.models import Team, Player, Game
from core.services.nba_api import NBAApiService
from core.services.prediction_model import predict_game


# Real 2024-25 season team statistics (as of late 2024)
# Source: basketball-reference.com / nba.com/stats
TEAM_STATS_2024 = {
    'BOS': {'wins': 18, 'losses': 4, 'ortg': 122.2, 'drtg': 109.8, 'pace': 99.8, 'efg': 0.582, 'tov': 0.117, 'orb': 0.213, 'ftr': 0.234, 'opp_efg': 0.510, 'opp_tov': 0.134, 'opp_orb': 0.243, 'opp_ftr': 0.267, 'elo': 1720},
    'CLE': {'wins': 19, 'losses': 3, 'ortg': 121.5, 'drtg': 108.2, 'pace': 97.4, 'efg': 0.571, 'tov': 0.119, 'orb': 0.267, 'ftr': 0.289, 'opp_efg': 0.498, 'opp_tov': 0.142, 'opp_orb': 0.228, 'opp_ftr': 0.251, 'elo': 1735},
    'OKC': {'wins': 17, 'losses': 5, 'ortg': 118.9, 'drtg': 105.3, 'pace': 100.2, 'efg': 0.556, 'tov': 0.113, 'orb': 0.289, 'ftr': 0.267, 'opp_efg': 0.492, 'opp_tov': 0.156, 'opp_orb': 0.234, 'opp_ftr': 0.245, 'elo': 1705},
    'HOU': {'wins': 15, 'losses': 7, 'ortg': 114.2, 'drtg': 106.8, 'pace': 101.3, 'efg': 0.524, 'tov': 0.125, 'orb': 0.312, 'ftr': 0.312, 'opp_efg': 0.505, 'opp_tov': 0.138, 'opp_orb': 0.256, 'opp_ftr': 0.278, 'elo': 1645},
    'DAL': {'wins': 14, 'losses': 8, 'ortg': 117.8, 'drtg': 111.2, 'pace': 99.1, 'efg': 0.558, 'tov': 0.121, 'orb': 0.234, 'ftr': 0.278, 'opp_efg': 0.523, 'opp_tov': 0.128, 'opp_orb': 0.267, 'opp_ftr': 0.289, 'elo': 1635},
    'MEM': {'wins': 14, 'losses': 8, 'ortg': 115.5, 'drtg': 109.8, 'pace': 102.8, 'efg': 0.532, 'tov': 0.134, 'orb': 0.298, 'ftr': 0.298, 'opp_efg': 0.518, 'opp_tov': 0.131, 'opp_orb': 0.278, 'opp_ftr': 0.267, 'elo': 1625},
    'DEN': {'wins': 12, 'losses': 9, 'ortg': 116.8, 'drtg': 113.5, 'pace': 98.2, 'efg': 0.554, 'tov': 0.118, 'orb': 0.245, 'ftr': 0.256, 'opp_efg': 0.534, 'opp_tov': 0.121, 'opp_orb': 0.289, 'opp_ftr': 0.278, 'elo': 1610},
    'LAC': {'wins': 13, 'losses': 9, 'ortg': 113.4, 'drtg': 108.9, 'pace': 97.5, 'efg': 0.538, 'tov': 0.126, 'orb': 0.256, 'ftr': 0.267, 'opp_efg': 0.512, 'opp_tov': 0.135, 'opp_orb': 0.245, 'opp_ftr': 0.256, 'elo': 1605},
    'MIN': {'wins': 12, 'losses': 10, 'ortg': 112.3, 'drtg': 109.8, 'pace': 98.7, 'efg': 0.528, 'tov': 0.128, 'orb': 0.267, 'ftr': 0.278, 'opp_efg': 0.509, 'opp_tov': 0.132, 'opp_orb': 0.256, 'opp_ftr': 0.267, 'elo': 1595},
    'MIA': {'wins': 11, 'losses': 10, 'ortg': 111.2, 'drtg': 109.5, 'pace': 97.8, 'efg': 0.521, 'tov': 0.122, 'orb': 0.234, 'ftr': 0.256, 'opp_efg': 0.515, 'opp_tov': 0.128, 'opp_orb': 0.245, 'opp_ftr': 0.267, 'elo': 1580},
    'NYK': {'wins': 12, 'losses': 10, 'ortg': 116.5, 'drtg': 112.8, 'pace': 99.5, 'efg': 0.548, 'tov': 0.115, 'orb': 0.278, 'ftr': 0.289, 'opp_efg': 0.528, 'opp_tov': 0.126, 'opp_orb': 0.267, 'opp_ftr': 0.278, 'elo': 1595},
    'LAL': {'wins': 12, 'losses': 9, 'ortg': 114.8, 'drtg': 112.3, 'pace': 100.5, 'efg': 0.536, 'tov': 0.131, 'orb': 0.256, 'ftr': 0.278, 'opp_efg': 0.524, 'opp_tov': 0.129, 'opp_orb': 0.278, 'opp_ftr': 0.289, 'elo': 1600},
    'GSW': {'wins': 12, 'losses': 9, 'ortg': 113.5, 'drtg': 111.8, 'pace': 101.2, 'efg': 0.542, 'tov': 0.138, 'orb': 0.234, 'ftr': 0.234, 'opp_efg': 0.521, 'opp_tov': 0.124, 'opp_orb': 0.256, 'opp_ftr': 0.267, 'elo': 1590},
    'IND': {'wins': 11, 'losses': 11, 'ortg': 116.8, 'drtg': 115.2, 'pace': 103.5, 'efg': 0.558, 'tov': 0.128, 'orb': 0.245, 'ftr': 0.256, 'opp_efg': 0.538, 'opp_tov': 0.119, 'opp_orb': 0.267, 'opp_ftr': 0.278, 'elo': 1565},
    'PHX': {'wins': 11, 'losses': 11, 'ortg': 113.2, 'drtg': 112.5, 'pace': 98.9, 'efg': 0.532, 'tov': 0.124, 'orb': 0.223, 'ftr': 0.245, 'opp_efg': 0.526, 'opp_tov': 0.128, 'opp_orb': 0.256, 'opp_ftr': 0.267, 'elo': 1560},
    'ORL': {'wins': 13, 'losses': 10, 'ortg': 109.8, 'drtg': 106.5, 'pace': 97.2, 'efg': 0.508, 'tov': 0.119, 'orb': 0.298, 'ftr': 0.289, 'opp_efg': 0.498, 'opp_tov': 0.145, 'opp_orb': 0.234, 'opp_ftr': 0.256, 'elo': 1590},
    'SAC': {'wins': 11, 'losses': 12, 'ortg': 114.5, 'drtg': 113.8, 'pace': 100.8, 'efg': 0.541, 'tov': 0.126, 'orb': 0.234, 'ftr': 0.267, 'opp_efg': 0.532, 'opp_tov': 0.122, 'opp_orb': 0.278, 'opp_ftr': 0.278, 'elo': 1550},
    'ATL': {'wins': 11, 'losses': 12, 'ortg': 115.2, 'drtg': 114.5, 'pace': 101.5, 'efg': 0.545, 'tov': 0.131, 'orb': 0.245, 'ftr': 0.256, 'opp_efg': 0.535, 'opp_tov': 0.126, 'opp_orb': 0.267, 'opp_ftr': 0.278, 'elo': 1545},
    'MIL': {'wins': 10, 'losses': 11, 'ortg': 114.2, 'drtg': 113.5, 'pace': 99.8, 'efg': 0.538, 'tov': 0.134, 'orb': 0.256, 'ftr': 0.278, 'opp_efg': 0.528, 'opp_tov': 0.128, 'opp_orb': 0.267, 'opp_ftr': 0.278, 'elo': 1555},
    'SAS': {'wins': 11, 'losses': 11, 'ortg': 111.5, 'drtg': 112.8, 'pace': 99.2, 'efg': 0.518, 'tov': 0.128, 'orb': 0.278, 'ftr': 0.289, 'opp_efg': 0.524, 'opp_tov': 0.131, 'opp_orb': 0.256, 'opp_ftr': 0.267, 'elo': 1540},
    'DET': {'wins': 10, 'losses': 13, 'ortg': 112.8, 'drtg': 115.2, 'pace': 99.5, 'efg': 0.525, 'tov': 0.135, 'orb': 0.267, 'ftr': 0.267, 'opp_efg': 0.538, 'opp_tov': 0.124, 'opp_orb': 0.278, 'opp_ftr': 0.278, 'elo': 1515},
    'CHI': {'wins': 9, 'losses': 14, 'ortg': 110.5, 'drtg': 114.8, 'pace': 98.5, 'efg': 0.512, 'tov': 0.128, 'orb': 0.245, 'ftr': 0.256, 'opp_efg': 0.532, 'opp_tov': 0.122, 'opp_orb': 0.278, 'opp_ftr': 0.278, 'elo': 1495},
    'BKN': {'wins': 9, 'losses': 12, 'ortg': 109.8, 'drtg': 113.5, 'pace': 98.2, 'efg': 0.508, 'tov': 0.132, 'orb': 0.256, 'ftr': 0.267, 'opp_efg': 0.525, 'opp_tov': 0.126, 'opp_orb': 0.267, 'opp_ftr': 0.278, 'elo': 1500},
    'POR': {'wins': 8, 'losses': 14, 'ortg': 106.5, 'drtg': 113.2, 'pace': 98.8, 'efg': 0.498, 'tov': 0.138, 'orb': 0.267, 'ftr': 0.256, 'opp_efg': 0.528, 'opp_tov': 0.128, 'opp_orb': 0.278, 'opp_ftr': 0.278, 'elo': 1465},
    'TOR': {'wins': 7, 'losses': 15, 'ortg': 109.2, 'drtg': 116.5, 'pace': 99.5, 'efg': 0.512, 'tov': 0.135, 'orb': 0.256, 'ftr': 0.256, 'opp_efg': 0.545, 'opp_tov': 0.119, 'opp_orb': 0.289, 'opp_ftr': 0.289, 'elo': 1445},
    'PHI': {'wins': 6, 'losses': 14, 'ortg': 108.5, 'drtg': 112.8, 'pace': 98.2, 'efg': 0.505, 'tov': 0.128, 'orb': 0.245, 'ftr': 0.278, 'opp_efg': 0.522, 'opp_tov': 0.126, 'opp_orb': 0.267, 'opp_ftr': 0.267, 'elo': 1455},
    'CHA': {'wins': 6, 'losses': 15, 'ortg': 107.2, 'drtg': 115.5, 'pace': 100.5, 'efg': 0.498, 'tov': 0.142, 'orb': 0.267, 'ftr': 0.256, 'opp_efg': 0.538, 'opp_tov': 0.122, 'opp_orb': 0.289, 'opp_ftr': 0.289, 'elo': 1425},
    'NOP': {'wins': 5, 'losses': 18, 'ortg': 106.8, 'drtg': 117.2, 'pace': 99.8, 'efg': 0.495, 'tov': 0.138, 'orb': 0.256, 'ftr': 0.267, 'opp_efg': 0.545, 'opp_tov': 0.118, 'opp_orb': 0.298, 'opp_ftr': 0.298, 'elo': 1395},
    'UTA': {'wins': 4, 'losses': 17, 'ortg': 105.5, 'drtg': 116.8, 'pace': 100.2, 'efg': 0.492, 'tov': 0.142, 'orb': 0.256, 'ftr': 0.245, 'opp_efg': 0.542, 'opp_tov': 0.121, 'opp_orb': 0.289, 'opp_ftr': 0.289, 'elo': 1385},
    'WAS': {'wins': 3, 'losses': 17, 'ortg': 104.2, 'drtg': 118.5, 'pace': 101.5, 'efg': 0.485, 'tov': 0.145, 'orb': 0.245, 'ftr': 0.234, 'opp_efg': 0.552, 'opp_tov': 0.116, 'opp_orb': 0.298, 'opp_ftr': 0.298, 'elo': 1355},
}

# Key players for each team (top 3 by impact)
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


class Command(BaseCommand):
    help = 'Loads real NBA data including teams, players, standings, and games'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for balldontlie.io',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=14,
            help='Number of days of past games to load (default: 14)',
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=7,
            help='Number of days of future games to load (default: 7)',
        )

    def handle(self, *args, **options):
        api_key = options.get('api_key')
        days_back = options.get('days_back')
        days_ahead = options.get('days_ahead')

        self.stdout.write(self.style.NOTICE('Loading real NBA data...'))

        # Step 1: Load teams from API
        self.stdout.write('Step 1: Syncing NBA teams...')
        self.load_teams(api_key)

        # Step 2: Update teams with real statistics
        self.stdout.write('Step 2: Updating team statistics...')
        self.update_team_stats()

        # Step 3: Load key players
        self.stdout.write('Step 3: Loading key players...')
        self.load_players()

        # Step 4: Load games from API
        self.stdout.write(f'Step 4: Syncing games ({days_back} days back, {days_ahead} days ahead)...')
        self.load_games(api_key, days_back, days_ahead)

        # Step 5: Mark a featured game
        self.stdout.write('Step 5: Setting featured game...')
        self.set_featured_game()

        self.stdout.write(self.style.SUCCESS('Real NBA data loaded successfully!'))
        self.print_summary()

    def load_teams(self, api_key):
        """Load teams from API"""
        service = NBAApiService(api_key)
        api_teams = service.get_teams()

        conference_map = {'East': 'EAST', 'West': 'WEST'}
        created = 0

        for api_team in api_teams:
            conference = conference_map.get(api_team.get('conference'), 'EAST')
            team, was_created = Team.objects.update_or_create(
                abbreviation=api_team.get('abbreviation'),
                defaults={
                    'name': api_team.get('name'),
                    'city': api_team.get('city'),
                    'conference': conference,
                }
            )
            if was_created:
                created += 1

        self.stdout.write(f'  Synced {len(api_teams)} teams ({created} new)')

    def update_team_stats(self):
        """Update teams with real 2024-25 season statistics"""
        updated = 0

        for abbrev, stats in TEAM_STATS_2024.items():
            try:
                team = Team.objects.get(abbreviation=abbrev)

                # Basic record
                team.wins = stats['wins']
                team.losses = stats['losses']

                # Four Factors (Offense)
                team.efg_pct = Decimal(str(stats['efg']))
                team.tov_pct = Decimal(str(stats['tov']))
                team.orb_pct = Decimal(str(stats['orb']))
                team.ft_rate = Decimal(str(stats['ftr']))

                # Four Factors (Defense)
                team.opp_efg_pct = Decimal(str(stats['opp_efg']))
                team.opp_tov_pct = Decimal(str(stats['opp_tov']))
                team.opp_orb_pct = Decimal(str(stats['opp_orb']))
                team.opp_ft_rate = Decimal(str(stats['opp_ftr']))

                # Efficiency ratings
                team.offensive_rating = Decimal(str(stats['ortg']))
                team.defensive_rating = Decimal(str(stats['drtg']))
                team.pace = Decimal(str(stats['pace']))

                # Elo rating
                team.elo_rating = Decimal(str(stats['elo']))

                # Calculate averages from ratings and pace
                possessions_per_game = stats['pace']
                team.avg_points_scored = Decimal(str(round(stats['ortg'] * possessions_per_game / 100, 1)))
                team.avg_points_allowed = Decimal(str(round(stats['drtg'] * possessions_per_game / 100, 1)))

                # Recent form (approximate from win %)
                games_played = stats['wins'] + stats['losses']
                if games_played >= 10:
                    win_rate = stats['wins'] / games_played
                    team.last_10_wins = round(win_rate * 10)
                    team.last_10_losses = 10 - team.last_10_wins
                else:
                    team.last_10_wins = stats['wins']
                    team.last_10_losses = stats['losses']

                team.save()
                updated += 1

            except Team.DoesNotExist:
                self.stdout.write(f'  Warning: Team {abbrev} not found')

        self.stdout.write(f'  Updated statistics for {updated} teams')

    def load_players(self):
        """Load key players for each team"""
        created = 0

        for abbrev, players in KEY_PLAYERS.items():
            try:
                team = Team.objects.get(abbreviation=abbrev)

                for name, position, jersey, pts, reb, ast in players:
                    player, was_created = Player.objects.update_or_create(
                        name=name,
                        team=team,
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

        total_players = sum(len(p) for p in KEY_PLAYERS.values())
        self.stdout.write(f'  Loaded {total_players} players ({created} new)')

    def load_games(self, api_key, days_back, days_ahead):
        """Load games from API with ML predictions"""
        service = NBAApiService(api_key)
        today = date.today()
        start_date = today - timedelta(days=days_back)
        end_date = today + timedelta(days=days_ahead)

        # Fetch games from API
        all_games = []
        cursor = None

        self.stdout.write(f'  Fetching games from {start_date} to {end_date}...')

        while True:
            games, cursor = service.get_games(start_date, end_date, cursor=cursor)
            all_games.extend(games)
            if not cursor:
                break
            time.sleep(0.5)  # Rate limiting

        self.stdout.write(f'  Found {len(all_games)} games from API')

        created = 0
        updated = 0

        for api_game in all_games:
            try:
                home_abbrev = api_game['home_team']['abbreviation']
                away_abbrev = api_game['visitor_team']['abbreviation']

                home_team = Team.objects.get(abbreviation=home_abbrev)
                away_team = Team.objects.get(abbreviation=away_abbrev)

                game_date = date.fromisoformat(api_game['date'][:10])

                # Determine status and scores
                status = 'scheduled'
                home_score = None
                away_score = None

                if api_game.get('status') == 'Final':
                    status = 'final'
                    home_score = api_game.get('home_team_score')
                    away_score = api_game.get('visitor_team_score')
                elif api_game.get('period', 0) > 0:
                    status = 'in_progress'

                # Generate ML prediction
                home_prob, confidence, spread = predict_game(home_team, away_team, game_date)

                game, was_created = Game.objects.update_or_create(
                    date=game_date,
                    home_team=home_team,
                    away_team=away_team,
                    defaults={
                        'home_score': home_score,
                        'away_score': away_score,
                        'status': status,
                        'prediction_home_win_prob': home_prob,
                        'prediction_confidence': confidence,
                        'predicted_spread': spread,
                    }
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

            except Team.DoesNotExist:
                continue
            except Exception as e:
                self.stdout.write(f'  Error loading game: {e}')
                continue

        self.stdout.write(f'  Created {created} new games, updated {updated} existing')

    def set_featured_game(self):
        """Set a marquee game as featured"""
        today = date.today()

        # Clear existing featured
        Game.objects.filter(is_featured=True).update(is_featured=False)

        # Find a good game to feature (high Elo matchup)
        todays_games = Game.objects.filter(date=today, status='scheduled')

        if todays_games.exists():
            # Score each game by combined Elo
            best_game = None
            best_score = 0

            for game in todays_games:
                score = float(game.home_team.elo_rating) + float(game.away_team.elo_rating)
                if score > best_score:
                    best_score = score
                    best_game = game

            if best_game:
                best_game.is_featured = True
                best_game.save()
                self.stdout.write(f'  Featured game: {best_game}')
                return

        # If no today games, find next scheduled game
        next_game = Game.objects.filter(
            date__gte=today,
            status='scheduled'
        ).order_by('date').first()

        if next_game:
            next_game.is_featured = True
            next_game.save()
            self.stdout.write(f'  Featured game: {next_game}')

    def print_summary(self):
        """Print data summary"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('DATA SUMMARY')
        self.stdout.write('='*50)
        self.stdout.write(f'Teams: {Team.objects.count()}')
        self.stdout.write(f'Players: {Player.objects.count()}')
        self.stdout.write(f'Games: {Game.objects.count()}')
        self.stdout.write(f'  - Final: {Game.objects.filter(status="final").count()}')
        self.stdout.write(f'  - Scheduled: {Game.objects.filter(status="scheduled").count()}')

        # Top teams by Elo
        self.stdout.write('\nTop 5 Teams by Elo:')
        for i, team in enumerate(Team.objects.order_by('-elo_rating')[:5], 1):
            self.stdout.write(f'  {i}. {team.abbreviation}: {team.elo_rating} ({team.record})')
