# tasks/management/commands/update_availability.py

from django.core.management.base import BaseCommand
from tasks.models import UserProfile
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Update availability for all user profiles to include 8 hours for each day'

    def handle(self, *args, **kwargs):
        profiles = UserProfile.objects.all()
        today = date.today()
        end_date = today + timedelta(days=365)  # Update for the next year

        for profile in profiles:
            availability = profile.availability
            current_date = today

            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                if date_str not in availability:
                    availability[date_str] = 8.0
                current_date += timedelta(days=1)

            profile.availability = availability
            profile.save()
            self.stdout.write(self.style.SUCCESS(f'Updated availability for user {profile.user.username}'))

        self.stdout.write(self.style.SUCCESS('All profiles updated successfully'))