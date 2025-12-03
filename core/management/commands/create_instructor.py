"""
Management command to create the instructor account.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Creates the instructor account (mohitg2/graingerlibrary)'

    def handle(self, *args, **options):
        username = 'mohitg2'
        password = 'graingerlibrary'
        email = 'mohitg2@illinois.edu'

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists.')
            )
            return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=True,  # Allow access to admin
        )

        # Create user profile
        UserProfile.objects.create(user=user)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created instructor account: {username}')
        )
