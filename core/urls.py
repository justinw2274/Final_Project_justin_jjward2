from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('teams/', views.TeamListView.as_view(), name='team_list'),
    path('teams/<int:pk>/', views.TeamDetailView.as_view(), name='team_detail'),
    path('games/<int:pk>/', views.game_detail, name='game_detail'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('export/', views.export_data, name='export'),

    # JSON API endpoints
    path('api/games/', views.api_games, name='api_games'),
    path('api/standings/', views.api_standings, name='api_standings'),
    path('api/teams/<str:abbreviation>/', views.api_team_stats, name='api_team_stats'),
]
