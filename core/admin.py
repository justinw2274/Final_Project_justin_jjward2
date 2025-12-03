from django.contrib import admin
from .models import Team, Player, Game, UserPick, UserProfile


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'abbreviation', 'conference', 'record', 'win_percentage']
    list_filter = ['conference']
    search_fields = ['name', 'city', 'abbreviation']
    ordering = ['conference', 'name']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'team', 'position', 'jersey_number', 'avg_points', 'avg_rebounds', 'avg_assists']
    list_filter = ['team', 'position']
    search_fields = ['name', 'team__name']
    ordering = ['team', 'name']


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['date', 'away_team', 'home_team', 'home_score', 'away_score', 'status', 'prediction_home_win_prob', 'is_featured']
    list_filter = ['status', 'date', 'is_featured']
    search_fields = ['home_team__name', 'away_team__name']
    date_hierarchy = 'date'
    ordering = ['-date']


@admin.register(UserPick)
class UserPickAdmin(admin.ModelAdmin):
    list_display = ['user', 'game', 'picked_team', 'is_correct', 'created_at']
    list_filter = ['created_at', 'picked_team']
    search_fields = ['user__username', 'game__home_team__name', 'game__away_team__name']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'favorite_team', 'total_picks', 'correct_picks', 'accuracy']
    list_filter = ['favorite_team']
    search_fields = ['user__username']
