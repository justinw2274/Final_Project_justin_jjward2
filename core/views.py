from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.db.models import Avg, Sum, Count, Q, F
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
import csv
import json
import io
import base64

from .models import Team, Player, Game, UserPick, UserProfile
from .forms import UserPickForm, ExportForm


def home(request):
    """Landing page with featured game of the night"""
    featured_game = Game.objects.filter(
        is_featured=True,
        date__gte=timezone.now().date()
    ).select_related('home_team', 'away_team').first()

    # Get upcoming games for preview
    upcoming_games = Game.objects.filter(
        date__gte=timezone.now().date(),
        status='scheduled'
    ).select_related('home_team', 'away_team').order_by('date', 'time')[:5]

    # Conference standings
    east_standings = Team.objects.filter(conference='EAST').order_by('-wins')[:5]
    west_standings = Team.objects.filter(conference='WEST').order_by('-wins')[:5]

    context = {
        'featured_game': featured_game,
        'upcoming_games': upcoming_games,
        'east_standings': east_standings,
        'west_standings': west_standings,
    }
    return render(request, 'core/home.html', context)


@login_required
def dashboard(request):
    """Main dashboard showing games with predictions"""
    today = timezone.now().date()

    # Get today's games
    todays_games = Game.objects.filter(
        date=today
    ).select_related('home_team', 'away_team').order_by('time')

    # Get upcoming games (next 7 days)
    upcoming_games = Game.objects.filter(
        date__gt=today,
        date__lte=today + timedelta(days=7),
        status='scheduled'
    ).select_related('home_team', 'away_team').order_by('date', 'time')

    # Recent results
    recent_games = Game.objects.filter(
        status='final',
        date__gte=today - timedelta(days=7)
    ).select_related('home_team', 'away_team').order_by('-date')[:10]

    # User's picks for displayed games
    user_picks = {}
    if request.user.is_authenticated:
        game_ids = list(todays_games.values_list('id', flat=True)) + list(upcoming_games.values_list('id', flat=True))
        picks = UserPick.objects.filter(user=request.user, game_id__in=game_ids)
        user_picks = {pick.game_id: pick.picked_team_id for pick in picks}

    context = {
        'todays_games': todays_games,
        'upcoming_games': upcoming_games,
        'recent_games': recent_games,
        'user_picks': user_picks,
    }
    return render(request, 'core/dashboard.html', context)


class TeamListView(ListView):
    """List all NBA teams"""
    model = Team
    template_name = 'core/team_list.html'
    context_object_name = 'teams'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['east_teams'] = Team.objects.filter(conference='EAST').order_by('-wins')
        context['west_teams'] = Team.objects.filter(conference='WEST').order_by('-wins')
        return context


class TeamDetailView(DetailView):
    """Team detail page with roster and recent performance"""
    model = Team
    template_name = 'core/team_detail.html'
    context_object_name = 'team'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object

        # Get team roster
        context['roster'] = Player.objects.filter(team=team).order_by('position', 'name')

        # Recent games (last 10)
        context['recent_games'] = Game.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            status='final'
        ).select_related('home_team', 'away_team').order_by('-date')[:10]

        # Upcoming games
        context['upcoming_games'] = Game.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            status='scheduled',
            date__gte=timezone.now().date()
        ).select_related('home_team', 'away_team').order_by('date')[:5]

        # Team stats
        home_stats = Game.objects.filter(home_team=team, status='final').aggregate(
            avg_scored=Avg('home_score'),
            avg_allowed=Avg('away_score'),
            total_games=Count('id')
        )
        away_stats = Game.objects.filter(away_team=team, status='final').aggregate(
            avg_scored=Avg('away_score'),
            avg_allowed=Avg('home_score'),
            total_games=Count('id')
        )

        context['home_stats'] = home_stats
        context['away_stats'] = away_stats

        return context


@login_required
def game_detail(request, pk):
    """Game detail page with prediction, chart, and user voting"""
    game = get_object_or_404(
        Game.objects.select_related('home_team', 'away_team'),
        pk=pk
    )

    # Handle user pick form
    user_pick = None
    if request.user.is_authenticated:
        user_pick = UserPick.objects.filter(user=request.user, game=game).first()

    if request.method == 'POST' and game.status == 'scheduled':
        form = UserPickForm(game, request.POST)
        if form.is_valid():
            picked_team = form.cleaned_data['picked_team']
            if user_pick:
                user_pick.picked_team = picked_team
                user_pick.save()
            else:
                UserPick.objects.create(
                    user=request.user,
                    game=game,
                    picked_team=picked_team
                )
                # Increment user's total picks count
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.total_picks += 1
                profile.save()
            messages.success(request, f"Your pick for {picked_team.name} has been saved!")
            return redirect('core:game_detail', pk=pk)
    else:
        form = UserPickForm(game)
        if user_pick:
            form.fields['picked_team'].initial = user_pick.picked_team

    # Get community picks
    community_picks = UserPick.objects.filter(game=game).values('picked_team').annotate(
        count=Count('id')
    )
    total_picks = sum(p['count'] for p in community_picks)
    pick_percentages = {}
    for pick in community_picks:
        if total_picks > 0:
            pick_percentages[pick['picked_team']] = round(pick['count'] / total_picks * 100, 1)

    # Generate chart data
    chart_data = generate_team_comparison_chart(game)

    context = {
        'game': game,
        'form': form,
        'user_pick': user_pick,
        'pick_percentages': pick_percentages,
        'total_picks': total_picks,
        'chart_data': chart_data,
    }
    return render(request, 'core/game_detail.html', context)


def generate_team_comparison_chart(game):
    """Generate comparison chart data for home vs away team"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np

        # Get team stats
        home_team = game.home_team
        away_team = game.away_team

        # Calculate stats from recent games
        home_recent = Game.objects.filter(
            Q(home_team=home_team) | Q(away_team=home_team),
            status='final'
        ).order_by('-date')[:10]

        away_recent = Game.objects.filter(
            Q(home_team=away_team) | Q(away_team=away_team),
            status='final'
        ).order_by('-date')[:10]

        # Calculate averages
        home_ppg = sum(
            g.home_score if g.home_team == home_team else g.away_score
            for g in home_recent if g.home_score and g.away_score
        ) / max(len(home_recent), 1)

        away_ppg = sum(
            g.home_score if g.home_team == away_team else g.away_score
            for g in away_recent if g.home_score and g.away_score
        ) / max(len(away_recent), 1)

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        categories = ['PPG', 'Win %', 'Home/Away Edge']
        home_values = [home_ppg, home_team.win_percentage * 100, 55]  # Home court advantage
        away_values = [away_ppg, away_team.win_percentage * 100, 45]

        x = np.arange(len(categories))
        width = 0.35

        bars1 = ax.bar(x - width/2, home_values, width, label=home_team.abbreviation, color='#1d428a')
        bars2 = ax.bar(x + width/2, away_values, width, label=away_team.abbreviation, color='#c8102e')

        ax.set_xlabel('Metrics')
        ax.set_ylabel('Values')
        ax.set_title(f'{away_team.abbreviation} @ {home_team.abbreviation} - Team Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()

        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom')

        for bar in bars2:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom')

        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()

        return image_base64

    except Exception as e:
        return None


@login_required
def leaderboard(request):
    """Leaderboards and analytics page"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    # Highest scoring teams (last 7 days) - ordered by PPG
    high_scoring_teams = Team.objects.annotate(
        recent_home_points=Sum('home_games__home_score', filter=Q(home_games__date__gte=week_ago, home_games__status='final')),
        recent_away_points=Sum('away_games__away_score', filter=Q(away_games__date__gte=week_ago, away_games__status='final')),
        recent_home_games=Count('home_games', filter=Q(home_games__date__gte=week_ago, home_games__status='final')),
        recent_away_games=Count('away_games', filter=Q(away_games__date__gte=week_ago, away_games__status='final')),
    ).annotate(
        total_recent_points=F('recent_home_points') + F('recent_away_points'),
        total_recent_games=F('recent_home_games') + F('recent_away_games'),
    ).exclude(total_recent_games=0).exclude(total_recent_games__isnull=True)

    # Calculate PPG in Python since Django doesn't support division well
    high_scoring_list = []
    for team in high_scoring_teams:
        if team.total_recent_games and team.total_recent_games > 0 and team.total_recent_points:
            team.ppg = round(team.total_recent_points / team.total_recent_games, 1)
            high_scoring_list.append(team)
    high_scoring_list.sort(key=lambda x: x.ppg, reverse=True)
    high_scoring_teams = high_scoring_list[:10]

    # Hot & Cold Teams (last 10 games record)
    all_teams = Team.objects.all()
    team_form_list = []
    for team in all_teams:
        # Get last 10 games for this team
        home_games = list(Game.objects.filter(home_team=team, status='final').order_by('-date')[:10])
        away_games = list(Game.objects.filter(away_team=team, status='final').order_by('-date')[:10])
        recent_games = sorted(home_games + away_games, key=lambda g: g.date, reverse=True)[:10]

        if len(recent_games) >= 5:  # Need at least 5 games
            wins = 0
            form = []
            for game in recent_games:
                if game.home_team == team:
                    won = game.home_score > game.away_score
                else:
                    won = game.away_score > game.home_score
                if won:
                    wins += 1
                form.append('W' if won else 'L')

            team_form_list.append({
                'team': team,
                'wins': wins,
                'losses': len(recent_games) - wins,
                'games': len(recent_games),
                'form': ''.join(form),
                'win_pct': wins / len(recent_games)
            })

    # Sort by win percentage for hot/cold
    team_form_list.sort(key=lambda x: x['win_pct'], reverse=True)
    hot_teams = team_form_list[:5]
    cold_teams = team_form_list[-5:][::-1]  # Reverse to show worst first

    # Biggest Upsets - games where underdog won by largest margin
    # Underdog = team with lower win probability prediction
    upset_games = []
    completed_with_predictions = Game.objects.filter(
        status='final',
        prediction_home_win_prob__isnull=False
    ).select_related('home_team', 'away_team')

    for game in completed_with_predictions:
        home_prob = float(game.prediction_home_win_prob)
        home_won = game.home_score > game.away_score
        margin = abs(game.home_score - game.away_score)

        # Check if underdog won
        if (home_prob < 50 and home_won) or (home_prob >= 50 and not home_won):
            # Calculate upset magnitude (lower probability = bigger upset)
            if home_won:
                underdog_prob = home_prob
                winner = game.home_team
                loser = game.away_team
                winner_score = game.home_score
                loser_score = game.away_score
            else:
                underdog_prob = 100 - home_prob
                winner = game.away_team
                loser = game.home_team
                winner_score = game.away_score
                loser_score = game.home_score

            upset_games.append({
                'game': game,
                'winner': winner,
                'loser': loser,
                'winner_score': winner_score,
                'loser_score': loser_score,
                'margin': margin,
                'underdog_prob': underdog_prob,
                'upset_score': (50 - underdog_prob) + margin  # Combined upset magnitude
            })

    # Sort by upset score and get top 5
    upset_games.sort(key=lambda x: x['upset_score'], reverse=True)
    biggest_upsets = upset_games[:5]

    # Model prediction accuracy (straight up)
    completed_games = Game.objects.filter(
        status='final',
        prediction_home_win_prob__isnull=False
    )
    total_predictions = completed_games.count()
    correct_predictions = sum(1 for g in completed_games if g.prediction_correct)
    model_accuracy = round(correct_predictions / max(total_predictions, 1) * 100, 1)

    # Team search functionality
    search_query = request.GET.get('q', '').strip()
    searched_team = None
    team_stats = None
    if search_query:
        # Search for a team
        searched_team = Team.objects.filter(
            Q(name__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(abbreviation__icontains=search_query)
        ).first()

        if searched_team:
            # Calculate comprehensive team stats for the season
            home_games = Game.objects.filter(home_team=searched_team, status='final')
            away_games = Game.objects.filter(away_team=searched_team, status='final')

            # Points stats
            home_points_for = home_games.aggregate(total=Sum('home_score'))['total'] or 0
            home_points_against = home_games.aggregate(total=Sum('away_score'))['total'] or 0
            away_points_for = away_games.aggregate(total=Sum('away_score'))['total'] or 0
            away_points_against = away_games.aggregate(total=Sum('home_score'))['total'] or 0

            total_games = home_games.count() + away_games.count()
            total_points_for = home_points_for + away_points_for
            total_points_against = home_points_against + away_points_against

            # Home/Away record
            home_wins = home_games.filter(home_score__gt=F('away_score')).count()
            home_losses = home_games.count() - home_wins
            away_wins = away_games.filter(away_score__gt=F('home_score')).count()
            away_losses = away_games.count() - away_wins

            # Recent form (last 10 games)
            recent_home = list(home_games.order_by('-date')[:10])
            recent_away = list(away_games.order_by('-date')[:10])
            recent_games = sorted(recent_home + recent_away, key=lambda g: g.date, reverse=True)[:10]
            recent_form = []
            for game in recent_games:
                if game.home_team == searched_team:
                    won = game.home_score > game.away_score
                else:
                    won = game.away_score > game.home_score
                recent_form.append('W' if won else 'L')

            # Upcoming games
            upcoming_games = Game.objects.filter(
                Q(home_team=searched_team) | Q(away_team=searched_team),
                status='scheduled'
            ).select_related('home_team', 'away_team').order_by('date')[:5]

            team_stats = {
                'games_played': total_games,
                'ppg': round(total_points_for / max(total_games, 1), 1),
                'opp_ppg': round(total_points_against / max(total_games, 1), 1),
                'point_diff': round((total_points_for - total_points_against) / max(total_games, 1), 1),
                'home_record': f"{home_wins}-{home_losses}",
                'away_record': f"{away_wins}-{away_losses}",
                'recent_form': ''.join(recent_form),
                'upcoming_games': upcoming_games,
            }

    # Top user predictors
    # Order by accuracy (for users with 10+ picks), then by total_picks for ties
    all_predictors = list(UserProfile.objects.filter(total_picks__gte=1))

    def predictor_sort_key(profile):
        # Users with 10+ picks: sort by accuracy (descending), then total_picks (descending)
        # Users with <10 picks: sort by total_picks only (they come after 10+ pick users)
        if profile.total_picks >= 10:
            # High priority (0), then by accuracy desc, then by total_picks desc
            return (0, -profile.accuracy, -profile.total_picks)
        else:
            # Low priority (1), then by total_picks desc
            return (1, 0, -profile.total_picks)

    all_predictors.sort(key=predictor_sort_key)
    top_users = all_predictors[:10]

    context = {
        'high_scoring_teams': high_scoring_teams,
        'hot_teams': hot_teams,
        'cold_teams': cold_teams,
        'biggest_upsets': biggest_upsets,
        'model_accuracy': model_accuracy,
        'total_predictions': total_predictions,
        'top_users': top_users,
        'search_query': search_query,
        'searched_team': searched_team,
        'team_stats': team_stats,
    }
    return render(request, 'core/leaderboard.html', context)


@login_required
def export_data(request):
    """Export predictions data as CSV or JSON"""
    if request.method == 'POST':
        form = ExportForm(request.POST)
        if form.is_valid():
            format_type = form.cleaned_data['format']
            date_range = form.cleaned_data['date_range']
            include_predictions = form.cleaned_data['include_predictions']
            include_user_picks = form.cleaned_data['include_user_picks']

            # Determine date filter
            today = timezone.now().date()
            if date_range == 'week':
                start_date = today - timedelta(days=7)
            elif date_range == 'month':
                start_date = today - timedelta(days=30)
            else:
                start_date = today - timedelta(days=365)

            # Query games
            games = Game.objects.filter(
                date__gte=start_date
            ).select_related('home_team', 'away_team').order_by('date')

            if format_type == 'csv':
                return export_csv(games, include_predictions, include_user_picks, request.user)
            else:
                return export_json(games, include_predictions, include_user_picks, request.user)
    else:
        form = ExportForm()

    context = {'form': form}
    return render(request, 'core/export.html', context)


def export_csv(games, include_predictions, include_user_picks, user):
    """Generate CSV export"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="courtvision_predictions.csv"'

    writer = csv.writer(response)

    # Header row
    headers = ['Date', 'Away Team', 'Home Team', 'Away Score', 'Home Score', 'Status']
    if include_predictions:
        headers.extend([
            'Home Win Prob %', 'Confidence %',
            'Pred Spread', 'Pred Total', 'Pred Home Score', 'Pred Away Score',
            'Vegas Spread', 'Vegas Total',
            'Prediction Correct'
        ])
    if include_user_picks:
        headers.append('Your Pick')
    writer.writerow(headers)

    # Get user picks if needed
    user_picks = {}
    if include_user_picks:
        picks = UserPick.objects.filter(user=user, game__in=games)
        user_picks = {p.game_id: p.picked_team.abbreviation for p in picks}

    # Data rows
    for game in games:
        row = [
            game.date.strftime('%Y-%m-%d'),
            game.away_team.abbreviation,
            game.home_team.abbreviation,
            game.away_score or '',
            game.home_score or '',
            game.status,
        ]
        if include_predictions:
            # Calculate predicted total
            pred_total = ''
            if game.predicted_home_score and game.predicted_away_score:
                pred_total = game.predicted_home_score + game.predicted_away_score
            row.extend([
                game.prediction_home_win_prob or '',
                game.prediction_confidence or '',
                game.predicted_spread or '',
                pred_total,
                game.predicted_home_score or '',
                game.predicted_away_score or '',
                game.vegas_spread if game.vegas_spread is not None else '',
                game.vegas_total if game.vegas_total is not None else '',
                'Yes' if game.prediction_correct else ('No' if game.prediction_correct is False else ''),
            ])
        if include_user_picks:
            row.append(user_picks.get(game.id, ''))
        writer.writerow(row)

    return response


def export_json(games, include_predictions, include_user_picks, user):
    """Generate JSON export"""
    user_picks = {}
    if include_user_picks:
        picks = UserPick.objects.filter(user=user, game__in=games)
        user_picks = {p.game_id: p.picked_team.abbreviation for p in picks}

    data = []
    for game in games:
        game_data = {
            'date': game.date.strftime('%Y-%m-%d'),
            'away_team': game.away_team.abbreviation,
            'home_team': game.home_team.abbreviation,
            'away_score': game.away_score,
            'home_score': game.home_score,
            'status': game.status,
        }
        if include_predictions:
            # Calculate predicted total
            pred_total = None
            if game.predicted_home_score and game.predicted_away_score:
                pred_total = game.predicted_home_score + game.predicted_away_score
            game_data['predictions'] = {
                'home_win_probability': float(game.prediction_home_win_prob) if game.prediction_home_win_prob else None,
                'confidence': float(game.prediction_confidence) if game.prediction_confidence else None,
                'spread': float(game.predicted_spread) if game.predicted_spread else None,
                'total': pred_total,
                'home_score': game.predicted_home_score,
                'away_score': game.predicted_away_score,
                'correct': game.prediction_correct,
            }
            game_data['vegas'] = {
                'spread': float(game.vegas_spread) if game.vegas_spread is not None else None,
                'total': float(game.vegas_total) if game.vegas_total is not None else None,
            }
        if include_user_picks:
            game_data['user_pick'] = user_picks.get(game.id)
        data.append(game_data)

    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="courtvision_predictions.json"'
    return response


# =============================================================================
# JSON API Endpoints
# =============================================================================

def api_games(request):
    """
    JSON API endpoint for games data.
    Returns structured JSON for charting and data sharing.

    Query params:
    - status: filter by status (scheduled, final, in_progress)
    - days: number of days to look back/ahead (default 7)
    """
    status_filter = request.GET.get('status', None)
    days = int(request.GET.get('days', 7))

    today = timezone.now().date()
    start_date = today - timedelta(days=days)
    end_date = today + timedelta(days=days)

    games = Game.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('home_team', 'away_team').order_by('date', 'time')

    if status_filter:
        games = games.filter(status=status_filter)

    data = {
        'count': games.count(),
        'generated_at': timezone.now().isoformat(),
        'games': []
    }

    for game in games:
        game_data = {
            'id': game.id,
            'date': game.date.isoformat(),
            'status': game.status,
            'home_team': {
                'name': game.home_team.name,
                'abbreviation': game.home_team.abbreviation,
                'record': game.home_team.record,
            },
            'away_team': {
                'name': game.away_team.name,
                'abbreviation': game.away_team.abbreviation,
                'record': game.away_team.record,
            },
            'scores': {
                'home': game.home_score,
                'away': game.away_score,
            },
            'prediction': {
                'home_win_prob': float(game.prediction_home_win_prob) if game.prediction_home_win_prob else None,
                'confidence': float(game.prediction_confidence) if game.prediction_confidence else None,
                'spread': float(game.predicted_spread) if game.predicted_spread else None,
                'predicted_home_score': game.predicted_home_score,
                'predicted_away_score': game.predicted_away_score,
            },
            'vegas': {
                'spread': float(game.vegas_spread) if game.vegas_spread else None,
                'total': float(game.vegas_total) if game.vegas_total else None,
            }
        }
        data['games'].append(game_data)

    return JsonResponse(data)


def api_standings(request):
    """
    JSON API endpoint for team standings.
    Returns structured JSON with conference standings.
    """
    east_teams = Team.objects.filter(conference='EAST').order_by('-wins')
    west_teams = Team.objects.filter(conference='WEST').order_by('-wins')

    def team_to_dict(team, rank):
        return {
            'rank': rank,
            'name': team.name,
            'city': team.city,
            'abbreviation': team.abbreviation,
            'wins': team.wins,
            'losses': team.losses,
            'win_pct': team.win_percentage,
            'record': team.record,
            'last_10': team.last_10_record,
            'streak': team.current_streak,
            'offensive_rating': float(team.offensive_rating),
            'defensive_rating': float(team.defensive_rating),
            'net_rating': team.net_rating,
        }

    data = {
        'generated_at': timezone.now().isoformat(),
        'eastern_conference': [team_to_dict(t, i+1) for i, t in enumerate(east_teams)],
        'western_conference': [team_to_dict(t, i+1) for i, t in enumerate(west_teams)],
    }

    return JsonResponse(data)


def api_team_stats(request, abbreviation):
    """
    JSON API endpoint for individual team statistics.
    Returns detailed team stats for charting.
    """
    team = get_object_or_404(Team, abbreviation=abbreviation.upper())

    # Get recent games
    recent_games = Game.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        status='final'
    ).order_by('-date')[:10]

    games_data = []
    for game in recent_games:
        is_home = game.home_team == team
        games_data.append({
            'date': game.date.isoformat(),
            'opponent': game.away_team.abbreviation if is_home else game.home_team.abbreviation,
            'home_away': 'home' if is_home else 'away',
            'team_score': game.home_score if is_home else game.away_score,
            'opponent_score': game.away_score if is_home else game.home_score,
            'result': 'W' if (is_home and game.home_score > game.away_score) or
                          (not is_home and game.away_score > game.home_score) else 'L',
        })

    data = {
        'team': {
            'name': team.name,
            'city': team.city,
            'abbreviation': team.abbreviation,
            'conference': team.conference,
            'record': team.record,
            'win_pct': team.win_percentage,
        },
        'stats': {
            'offensive_rating': float(team.offensive_rating),
            'defensive_rating': float(team.defensive_rating),
            'net_rating': team.net_rating,
            'pace': float(team.pace),
            'efg_pct': float(team.efg_pct),
            'tov_pct': float(team.tov_pct),
            'orb_pct': float(team.orb_pct),
            'ft_rate': float(team.ft_rate),
        },
        'recent_games': games_data,
    }

    return JsonResponse(data)
