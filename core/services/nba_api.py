"""
NBA API Service
Fetches data from balldontlie.io API
"""
import requests
from datetime import datetime, timedelta
from decimal import Decimal
import random


class NBAApiService:
    """Service to fetch NBA data from balldontlie.io API"""

    BASE_URL = "https://api.balldontlie.io/v1"

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = api_key

    def _make_request(self, endpoint, params=None):
        """Make a GET request to the API"""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return None

    def get_teams(self):
        """Fetch all NBA teams"""
        data = self._make_request("teams")
        if data:
            return data.get('data', [])
        return []

    def get_players(self, team_id=None, per_page=100):
        """Fetch NBA players, optionally filtered by team"""
        params = {'per_page': per_page}
        if team_id:
            params['team_ids[]'] = team_id
        data = self._make_request("players", params)
        if data:
            return data.get('data', [])
        return []

    def get_games(self, start_date=None, end_date=None, team_ids=None):
        """Fetch NBA games within date range"""
        params = {'per_page': 100}
        if start_date:
            params['start_date'] = start_date.strftime('%Y-%m-%d')
        if end_date:
            params['end_date'] = end_date.strftime('%Y-%m-%d')
        if team_ids:
            params['team_ids[]'] = team_ids

        data = self._make_request("games", params)
        if data:
            return data.get('data', [])
        return []

    def get_season_averages(self, player_ids, season=2024):
        """Fetch season averages for players"""
        params = {
            'season': season,
            'player_ids[]': player_ids
        }
        data = self._make_request("season_averages", params)
        if data:
            return data.get('data', [])
        return []


def sync_teams_from_api(api_key=None):
    """Sync teams from the NBA API to local database"""
    from core.models import Team

    service = NBAApiService(api_key)
    api_teams = service.get_teams()

    # Map API conference values to our model
    conference_map = {
        'East': 'EAST',
        'West': 'WEST',
    }

    created_count = 0
    for api_team in api_teams:
        conference = conference_map.get(api_team.get('conference'), 'EAST')

        team, created = Team.objects.update_or_create(
            abbreviation=api_team.get('abbreviation'),
            defaults={
                'name': api_team.get('name'),
                'city': api_team.get('city'),
                'conference': conference,
            }
        )
        if created:
            created_count += 1

    return created_count


def sync_games_from_api(api_key=None, days_ahead=7, days_back=7):
    """Sync games from the NBA API to local database"""
    from core.models import Team, Game

    service = NBAApiService(api_key)
    today = datetime.now().date()
    start_date = today - timedelta(days=days_back)
    end_date = today + timedelta(days=days_ahead)

    api_games = service.get_games(start_date, end_date)

    created_count = 0
    for api_game in api_games:
        try:
            home_team = Team.objects.get(abbreviation=api_game['home_team']['abbreviation'])
            away_team = Team.objects.get(abbreviation=api_game['visitor_team']['abbreviation'])

            game_date = datetime.strptime(api_game['date'][:10], '%Y-%m-%d').date()

            # Determine status
            status = 'scheduled'
            if api_game.get('status') == 'Final':
                status = 'final'
            elif api_game.get('period', 0) > 0:
                status = 'in_progress'

            # Generate prediction (simulated ML model)
            home_win_prob, confidence, spread = generate_prediction(home_team, away_team)

            game, created = Game.objects.update_or_create(
                date=game_date,
                home_team=home_team,
                away_team=away_team,
                defaults={
                    'home_score': api_game.get('home_team_score') if status == 'final' else None,
                    'away_score': api_game.get('visitor_team_score') if status == 'final' else None,
                    'status': status,
                    'prediction_home_win_prob': home_win_prob,
                    'prediction_confidence': confidence,
                    'predicted_spread': spread,
                }
            )
            if created:
                created_count += 1
        except Team.DoesNotExist:
            continue
        except Exception as e:
            print(f"Error syncing game: {e}")
            continue

    return created_count


def generate_prediction(home_team, away_team):
    """
    Generate a prediction for a game.
    This simulates an ML model prediction based on team records.
    In production, this would use actual ML model.
    """
    # Base home court advantage
    home_advantage = 0.54

    # Adjust based on win percentages
    home_wp = home_team.win_percentage
    away_wp = away_team.win_percentage

    if home_wp + away_wp > 0:
        wp_factor = (home_wp - away_wp) * 0.3
    else:
        wp_factor = 0

    # Calculate probability
    base_prob = home_advantage + wp_factor
    # Add some randomness to simulate model uncertainty
    noise = random.uniform(-0.1, 0.1)
    home_win_prob = max(0.20, min(0.80, base_prob + noise))

    # Confidence based on how different the teams are
    confidence = 50 + abs(home_wp - away_wp) * 30 + random.uniform(-10, 10)
    confidence = max(40, min(85, confidence))

    # Spread calculation (positive = home favored)
    spread = (home_win_prob - 0.5) * 20 + random.uniform(-2, 2)

    return (
        Decimal(str(round(home_win_prob * 100, 2))),
        Decimal(str(round(confidence, 2))),
        Decimal(str(round(spread, 1)))
    )
