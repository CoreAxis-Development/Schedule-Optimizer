from django.core.management.base import BaseCommand
from tasks.models import UserProfile

class Command(BaseCommand):
    help = 'Fix availability values to ensure no day has more than 8 hours of availability'

    def handle(self, *args, **kwargs):
        profiles = UserProfile.objects.all()
        for profile in profiles:
            availability = profile.availability
            updated = False
            for date_str, hours in availability.items():
                if hours > 8.0:
                    availability[date_str] = 8.0
                    updated = True
            if updated:
                profile.availability = availability
                profile.save()
                self.stdout.write(self.style.SUCCESS(f'Updated availability for user {profile.user.username}'))
        self.stdout.write(self.style.SUCCESS('All profiles updated successfully'))