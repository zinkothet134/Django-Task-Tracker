"""Run: python manage.py test tasks.test_mobile_update"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Task


class MobileTaskUpdateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='mobileowner', email='owner@example.net', password='SecretTest123!')
        self.assignee = User.objects.create_user(username='mobileassignee', email='assignee@example.net', password='SecretTest123!')
        self.other = User.objects.create_user(username='mobileother', email='other@example.net', password='SecretTest123!')
        self.task = Task.objects.create(title='Before', description='Original', status='TODO', priority='MEDIUM',
                                        visibility=Task.PERSONAL, created_by=self.owner, assigned_to=self.assignee)
        self.url = reverse('mobile_task_update', args=[self.task.pk])
        self.client = APIClient()

    def login(self, user):
        access = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def payload(self):
        self.task.refresh_from_db()
        return {'base_updated_at': self.task.updated_at.isoformat(), 'title': 'Updated',
                'description': 'Activity note', 'status': 'IN_PROGRESS', 'priority': 'HIGH'}

    def test_requires_authentication(self):
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 401)

    def test_creator_can_update_and_stale_version_conflicts(self):
        self.login(self.owner)
        data = self.payload()
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['task']['title'], 'Updated')
        # Even a replay cannot overwrite the updated server version.
        stale = self.client.post(self.url, dict(data, title='Stale overwrite'), format='json')
        self.assertEqual(stale.status_code, 409)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated')

    def test_assignee_may_update(self):
        self.login(self.assignee)
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_other_user_cannot_edit(self):
        self.login(self.other)
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 404)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Before')

    def test_rejects_ownership_change(self):
        self.login(self.owner)
        data = self.payload()
        data['assigned_to_id'] = self.other.pk
        # Explicitly reject the supplied extra field instead of silently ignoring it.
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to_id, self.assignee.pk)
