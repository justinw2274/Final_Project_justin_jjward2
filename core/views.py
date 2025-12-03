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

    # Highest scoring teams (last 7 days)
    high_scoring_teams = Team.objects.annotate(
        recent_home_points=Sum('home_games__home_score', filter=Q(home_games__date__gte=week_ago, home_games__status='final')),
        recent_away_points=Sum('away_games__away_score', filter=Q(away_games__date__gte=week_ago, away_games__status='final')),
    ).annotate(
        total_recent_points=F('recent_home_points') + F('recent_away_points')
    ).exclude(total_recent_points__isnull=True).order_by('-total_recent_points')[:10]

    # Conference standings
    east_standings = Team.objects.filter(conference='EAST').order_by('-wins')
    west_standings = Team.objects.filter(conference='WEST').order_by('-wins')

    # Model prediction accuracy
    completed_games = Game.objects.filter(
        status='final',
        prediction_home_win_prob__isnull=False
    )
    total_predictions = completed_games.count()
    correct_predictions = sum(1 for g in completed_games if g.prediction_correct)
    model_accuracy = round(correct_predictions / max(total_predictions, 1) * 100, 1)

    # Top user predictors
    top_users = UserProfile.objects.filter(
        total_picks__gte=5
    ).order_by('-correct_picks')[:10]

    # Average point differential by conference
    east_diff = Game.objects.filter(
        home_team__conference='EAST',
        status='final'
    ).aggregate(avg_diff=Avg(F('home_score') - F('away_score')))

    west_diff = Game.objects.filter(
        home_team__conference='WEST',
        status='final'
    ).aggregate(avg_diff=Avg(F('home_score') - F('away_score')))

    context = {
        'high_scoring_teams': high_scoring_teams,
        'east_standings': east_standings,
        'west_standings': west_standings,
        'model_accuracy': model_accuracy,
        'total_predictions': total_predictions,
        'top_users': top_users,
        'east_avg_diff': east_diff['avg_diff'] or 0,
        'west_avg_diff': west_diff['avg_diff'] or 0,
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
        headers.extend(['Home Win Prob %', 'Confidence %', 'Spread', 'Prediction Correct'])
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
            row.extend([
                game.prediction_home_win_prob or '',
                game.prediction_confidence or '',
                game.predicted_spread or '',
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
            game_data['predictions'] = {
                'home_win_probability': float(game.prediction_home_win_prob) if game.prediction_home_win_prob else None,
                'confidence': float(game.prediction_confidence) if game.prediction_confidence else None,
                'spread': float(game.predicted_spread) if game.predicted_spread else None,
                'correct': game.prediction_correct,
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
