"""
NBA API Service
Fetches data from balldontlie.io API and calculates advanced statistics.
"""
import requests
from datetime import datetime, timedelta, date
from decimal import Decimal
from .prediction_model import predict_game, NBAPredictor


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

    def get_players(self, team_id=None, per_page=100, cursor=None):
        """Fetch NBA players, optionally filtered by team"""
        params = {'per_page': per_page}
        if team_id:
            params['team_ids[]'] = team_id
        if cursor:
            params['cursor'] = cursor
        data = self._make_request("players", params)
        if data:
            return data.get('data', []), data.get('meta', {}).get('next_cursor')
        return [], None

    def get_games(self, start_date=None, end_date=None, team_ids=None, per_page=100, cursor=None):
        """Fetch NBA games within date range"""
        params = {'per_page': per_page}
        if start_date:
            params['start_date'] = start_date.strftime('%Y-%m-%d')
        if end_date:
            params['end_date'] = end_date.strftime('%Y-%m-%d')
        if team_ids:
            params['team_ids[]'] = team_ids
        if cursor:
            params['cursor'] = cursor

        data = self._make_request("games", params)
        if data:
            return data.get('data', []), data.get('meta', {}).get('next_cursor')
        return [], None

    def get_stats(self, game_ids=None, player_ids=None, per_page=100, cursor=None):
        """Fetch player box score stats"""
        params = {'per_page': per_page}
        if game_ids:
            params['game_ids[]'] = game_ids
        if player_ids:
            params['player_ids[]'] = player_ids
        if cursor:
            params['cursor'] = cursor

        data = self._make_request("stats", params)
        if data:
            return data.get('data', []), data.get('meta', {}).get('next_cursor')
        return [], None

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

    def get_standings(self, season=2024):
        """Fetch team standings"""
        params = {'season': season}
        data = self._make_request("standings", params)
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


def sync_games_from_api(api_key=None, days_ahead=7, days_back=30):
    """Sync games from the NBA API to local database with predictions"""
    from core.models import Team, Game

    service = NBAApiService(api_key)
    today = datetime.now().date()
    start_date = today - timedelta(days=days_back)
    end_date = today + timedelta(days=days_ahead)

    # Fetch all games in date range
    all_games = []
    cursor = None
    while True:
        games, cursor = service.get_games(start_date, end_date, cursor=cursor)
        all_games.extend(games)
        if not cursor:
            break

    created_count = 0
    updated_count = 0

    for api_game in all_games:
        try:
            home_team = Team.objects.get(abbreviation=api_game['home_team']['abbreviation'])
            away_team = Team.objects.get(abbreviation=api_game['visitor_team']['abbreviation'])

            game_date = datetime.strptime(api_game['date'][:10], '%Y-%m-%d').date()

            # Determine status
            status = 'scheduled'
            home_score = None
            away_score = None

            if api_game.get('status') == 'Final':
                status = 'final'
                home_score = api_game.get('home_team_score')
                away_score = api_game.get('visitor_team_score')
            elif api_game.get('period', 0) > 0:
                status = 'in_progress'

            # Generate prediction using ML model
            home_win_prob, confidence, spread, pred_home_score, pred_away_score = predict_game(home_team, away_team, game_date)

            game, created = Game.objects.update_or_create(
                date=game_date,
                home_team=home_team,
                away_team=away_team,
                defaults={
                    'home_score': home_score,
                    'away_score': away_score,
                    'status': status,
                    'prediction_home_win_prob': home_win_prob,
                    'prediction_confidence': confidence,
                    'predicted_spread': spread,
                    'predicted_home_score': pred_home_score,
                    'predicted_away_score': pred_away_score,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            # Update team records and Elo for completed games
            if status == 'final' and home_score is not None and away_score is not None:
                update_team_after_game(home_team, away_team, home_score, away_score, game_date)
                # Evaluate user picks for this game
                evaluate_user_picks_for_game(game)

        except Team.DoesNotExist:
            continue
        except Exception as e:
            print(f"Error syncing game: {e}")
            continue

    return created_count, updated_count


def update_team_after_game(home_team, away_team, home_score, away_score, game_date):
    """Update team statistics after a completed game"""
    predictor = NBAPredictor()

    # Determine winner and margin
    if home_score > away_score:
        winner = home_team
        loser = away_team
        margin = home_score - away_score
    else:
        winner = away_team
        loser = home_team
        margin = away_score - home_score

    # Update Elo ratings
    predictor.update_elo_after_game(winner, loser, home_team, margin)

    # Update last game date
    home_team.last_game_date = game_date
    away_team.last_game_date = game_date

    # Update average points
    if home_team.wins + home_team.losses > 0:
        games_played = home_team.wins + home_team.losses
        home_team.avg_points_scored = Decimal(str(round(
            (float(home_team.avg_points_scored) * (games_played - 1) + home_score) / games_played, 1
        )))
        home_team.avg_points_allowed = Decimal(str(round(
            (float(home_team.avg_points_allowed) * (games_played - 1) + away_score) / games_played, 1
        )))

    if away_team.wins + away_team.losses > 0:
        games_played = away_team.wins + away_team.losses
        away_team.avg_points_scored = Decimal(str(round(
            (float(away_team.avg_points_scored) * (games_played - 1) + away_score) / games_played, 1
        )))
        away_team.avg_points_allowed = Decimal(str(round(
            (float(away_team.avg_points_allowed) * (games_played - 1) + home_score) / games_played, 1
        )))

    home_team.save()
    away_team.save()


def calculate_team_advanced_stats(team, games, box_scores):
    """
    Calculate advanced statistics for a team based on game data.

    This calculates the Four Factors and efficiency ratings from raw box score data.
    """
    if not games or not box_scores:
        return

    total_fgm = 0
    total_fga = 0
    total_3pm = 0
    total_ftm = 0
    total_fta = 0
    total_orb = 0
    total_drb = 0
    total_tov = 0
    total_pts_scored = 0
    total_pts_allowed = 0
    total_possessions = 0

    # Opponent stats
    opp_fgm = 0
    opp_fga = 0
    opp_3pm = 0
    opp_ftm = 0
    opp_fta = 0
    opp_orb = 0
    opp_tov = 0

    for game in games:
        is_home = game['home_team']['abbreviation'] == team.abbreviation

        # Get team and opponent stats from box scores
        team_stats = box_scores.get(game['id'], {}).get('team' if is_home else 'opponent', {})
        opp_stats = box_scores.get(game['id'], {}).get('opponent' if is_home else 'team', {})

        if team_stats:
            total_fgm += team_stats.get('fgm', 0)
            total_fga += team_stats.get('fga', 0)
            total_3pm += team_stats.get('fg3m', 0)
            total_ftm += team_stats.get('ftm', 0)
            total_fta += team_stats.get('fta', 0)
            total_orb += team_stats.get('oreb', 0)
            total_drb += team_stats.get('dreb', 0)
            total_tov += team_stats.get('turnover', 0)

            if is_home:
                total_pts_scored += game.get('home_team_score', 0)
                total_pts_allowed += game.get('visitor_team_score', 0)
            else:
                total_pts_scored += game.get('visitor_team_score', 0)
                total_pts_allowed += game.get('home_team_score', 0)

        if opp_stats:
            opp_fgm += opp_stats.get('fgm', 0)
            opp_fga += opp_stats.get('fga', 0)
            opp_3pm += opp_stats.get('fg3m', 0)
            opp_ftm += opp_stats.get('ftm', 0)
            opp_fta += opp_stats.get('fta', 0)
            opp_orb += opp_stats.get('oreb', 0)
            opp_tov += opp_stats.get('turnover', 0)

    # Calculate Four Factors
    if total_fga > 0:
        # eFG% = (FGM + 0.5 * 3PM) / FGA
        team.efg_pct = Decimal(str(round((total_fgm + 0.5 * total_3pm) / total_fga, 3)))

        # FT Rate = FTA / FGA
        team.ft_rate = Decimal(str(round(total_fta / total_fga, 3)))

    # TOV% = TOV / (FGA + 0.44 * FTA + TOV)
    possessions_proxy = total_fga + 0.44 * total_fta + total_tov
    if possessions_proxy > 0:
        team.tov_pct = Decimal(str(round(total_tov / possessions_proxy, 3)))

    # ORB% = ORB / (ORB + Opp DRB)
    total_reb_opportunities = total_orb + (opp_fga - opp_fgm)  # Approximate opponent DRB
    if total_reb_opportunities > 0:
        team.orb_pct = Decimal(str(round(total_orb / total_reb_opportunities, 3)))

    # Calculate opponent Four Factors
    if opp_fga > 0:
        team.opp_efg_pct = Decimal(str(round((opp_fgm + 0.5 * opp_3pm) / opp_fga, 3)))
        team.opp_ft_rate = Decimal(str(round(opp_fta / opp_fga, 3)))

    opp_poss_proxy = opp_fga + 0.44 * opp_fta + opp_tov
    if opp_poss_proxy > 0:
        team.opp_tov_pct = Decimal(str(round(opp_tov / opp_poss_proxy, 3)))

    opp_reb_opp = opp_orb + total_drb
    if opp_reb_opp > 0:
        team.opp_orb_pct = Decimal(str(round(opp_orb / opp_reb_opp, 3)))

    # Estimate pace and ratings
    num_games = len(games)
    if num_games > 0:
        avg_possessions = possessions_proxy / num_games
        team.pace = Decimal(str(round(avg_possessions * 2, 1)))  # Approximate pace

        if avg_possessions > 0:
            team.offensive_rating = Decimal(str(round(
                (total_pts_scored / num_games) / (avg_possessions / 100) * 100, 1
            )))
            team.defensive_rating = Decimal(str(round(
                (total_pts_allowed / num_games) / (avg_possessions / 100) * 100, 1
            )))

    team.save()


def evaluate_user_picks_for_game(game):
    """
    Evaluate all user picks for a completed game and update user stats.
    Should be called when a game status changes to 'final'.
    Only processes picks that haven't been evaluated yet to prevent double-counting.
    """
    from core.models import UserPick, UserProfile

    if game.status != 'final' or game.winner is None:
        return 0

    updated_count = 0
    # Only get picks that haven't been evaluated yet
    picks = UserPick.objects.filter(game=game, evaluated=False).select_related('user')

    for pick in picks:
        if pick.picked_team == game.winner:
            # User got it right - increment their correct_picks
            profile, _ = UserProfile.objects.get_or_create(user=pick.user)
            profile.correct_picks += 1
            profile.save()
            updated_count += 1

        # Mark pick as evaluated regardless of outcome
        pick.evaluated = True
        pick.save()

    return updated_count
