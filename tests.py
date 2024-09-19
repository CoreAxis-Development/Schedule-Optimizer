from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from tasks.models import UserProfile

class AllYearlyTasksTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(username='great', password='testpassword')
        UserProfile.objects.create(user=self.user, availability={})
        self.client = Client()
        self.client.login(username='great', password='testpassword')

    def test_all_yearly_tasks(self):
        response = self.client.post(reverse('all_yearly_tasks'), {'year': 2024, 'filter': {}})
        self.assertEqual(response.status_code, 200)
        self.assertIn('year', response.json())  
