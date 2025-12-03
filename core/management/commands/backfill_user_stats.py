"""
Management command to backfill user pick statistics.
This recalculates total_picks and correct_picks for all users based on their UserPick records.
Also marks all picks for completed games as evaluated.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserPick, UserProfile


class Command(BaseCommand):
    help = 'Backfill user pick statistics (total_picks and correct_picks)'

    def handle(self, *args, **options):
        self.stdout.write("Backfilling user pick statistics...")

        # Get all users with picks
        users_with_picks = User.objects.filter(picks__isnull=False).distinct()

        updated_count = 0
        for user in users_with_picks:
            # Get or create profile
            profile, _ = UserProfile.objects.get_or_create(user=user)

            # Count total picks
            total = UserPick.objects.filter(user=user).count()

            # Count correct picks (only for completed games)
            correct = 0
            picks = UserPick.objects.filter(user=user).select_related('game', 'picked_team')
            for pick in picks:
                if pick.game.status == 'final':
                    # Mark as evaluated since game is complete
                    if not pick.evaluated:
                        pick.evaluated = True
                        pick.save()
                    # Check if correct
                    if pick.game.winner == pick.picked_team:
                        correct += 1

            # Update profile
            profile.total_picks = total
            profile.correct_picks = correct
            profile.save()

            self.stdout.write(f"  {user.username}: {total} picks, {correct} correct")
            updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully updated {updated_count} user profiles"
        ))
