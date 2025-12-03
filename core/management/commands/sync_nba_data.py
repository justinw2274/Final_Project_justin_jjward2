"""
Management command to sync data from NBA API.
"""
from django.core.management.base import BaseCommand
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

        self.stdout.write(self.style.SUCCESS('Sync completed!'))
