from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from tasks.models import Task


class MobileReadOnlyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='mobileowner', email='owner@example.com', password='testingPassword123!')
        self.other = User.objects.create_user(username='mobileother', email='other@example.com', password='testingPassword123!')
        self.mine = Task.objects.create(title='Allowed personal task', created_by=self.owner, assigned_to=self.owner)
        self.secret = Task.objects.create(title='Other private task', created_by=self.other, assigned_to=self.other)
        self.client = APIClient()

    def test_unauthenticated_denied(self):
        self.assertEqual(self.client.get('/api/mobile/tasks/').status_code, 401)

    def test_login_and_task_visibility(self):
        response = self.client.post('/api/mobile/login/', {'username': 'owner@example.com', 'password': 'testingPassword123!'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        result = self.client.get('/api/mobile/tasks/')
        self.assertEqual(result.status_code, 200)
        ids = [task['id'] for task in result.data['results']]
        self.assertIn(self.mine.pk, ids)
        self.assertNotIn(self.secret.pk, ids)

    def test_tasks_endpoint_readonly(self):
        response = self.client.post('/api/mobile/login/', {'username': 'mobileowner', 'password': 'testingPassword123!'}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        self.assertEqual(self.client.post('/api/mobile/tasks/', {'title': 'Not allowed'}, format='json').status_code, 405)
