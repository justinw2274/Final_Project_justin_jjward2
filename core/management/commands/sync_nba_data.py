"""
Management command to sync data from NBA API.
"""
from django.core.management.base import BaseCommand
from django.utils.timezone import localdate
from core.services.nba_api import sync_teams_from_api, sync_games_from_api


class Command(BaseCommand):
    help = 'Syncs NBA data from the balldontlie.io API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for balldontlie.io (optional)',
        )
        parser.add_argument(
            '--teams-only',
            action='store_true',
            help='Only sync teams',
        )
        parser.add_argument(
            '--games-only',
            action='store_true',
            help='Only sync games',
        )

    def handle(self, *args, **options):
        api_key = options.get('api_key')
        teams_only = options.get('teams_only')
        games_only = options.get('games_only')

        if not teams_only and not games_only:
            # Sync both
            teams_only = True
            games_only = True

        if teams_only:
            self.stdout.write('Syncing teams from API...')
            try:
                count = sync_teams_from_api(api_key)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {count} new teams')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error syncing teams: {e}')
                )

        if games_only:
            self.stdout.write('Syncing games from API...')
            try:
                count = sync_games_from_api(api_key)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {count} new games')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error syncing games: {e}')
                )

        # Auto-select featured game for today
        self.stdout.write('Updating featured game...')
        try:
            featured = self.set_featured_game()
            if featured:
                self.stdout.write(
                    self.style.SUCCESS(f'Featured game: {featured}')
                )
            else:
                self.stdout.write('No games today to feature')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error setting featured game: {e}')
            )

        self.stdout.write(self.style.SUCCESS('Sync completed!'))

    def set_featured_game(self):
        """
        Automatically select the best game to feature for today.
        Picks the matchup with the highest combined team wins (best quality game).
        """
        from core.models import Game

        today = localdate()

        # Clear old featured games
        Game.objects.filter(is_featured=True).update(is_featured=False)

        # Get today's scheduled games
        todays_games = Game.objects.filter(
            date=today,
            status='scheduled'
        ).select_related('home_team', 'away_team')

        if not todays_games.exists():
            return None

        # Find best matchup (highest combined wins = best teams playing)
        best_game = None
        best_score = -1

        for game in todays_games:
            combined_wins = game.home_team.wins + game.away_team.wins
            if combined_wins > best_score:
                best_score = combined_wins
                best_game = game

        if best_game:
            best_game.is_featured = True
            best_game.save()
            return f"{best_game.away_team.abbreviation} @ {best_game.home_team.abbreviation}"

        return None
