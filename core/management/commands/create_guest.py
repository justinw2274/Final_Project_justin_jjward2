"""
Management command to create the guest account.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Creates the guest account (infoadmins/uiucinfo)'

    def handle(self, *args, **options):
        username = 'infoadmins'
        password = 'uiucinfo'
        email = 'infoadmins@illinois.edu'

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists.')
            )
            return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        # Create user profile
        UserProfile.objects.create(user=user)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created guest account: {username}')
        )
