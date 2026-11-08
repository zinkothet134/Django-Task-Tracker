"""Run with: python3 manage.py test tasks.test_task_delete"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Task


class TaskDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.creator = User.objects.create_user(username="delete_creator", password="test-pass-123")
        cls.assignee = User.objects.create_user(username="delete_assignee", password="test-pass-123")
        cls.superuser = User.objects.create_superuser(
            username="delete_admin", email="admin@example.com", password="test-pass-123"
        )
        cls.task = Task.objects.create(
            title="Delegated task", created_by=cls.creator, assigned_to=cls.assignee
        )

    def url(self):
        return reverse("tasks:task_delete", args=[self.task.pk])

    def test_creator_sees_confirmation_without_deleting(self):
        self.client.force_login(self.creator)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_creator_must_confirm(self):
        self.client.force_login(self.creator)
        response = self.client.post(self.url(), {})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Tick the confirmation", status_code=400)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_creator_can_delete(self):
        self.client.force_login(self.creator)
        response = self.client.post(self.url(), {"confirm_delete": "yes"})
        self.assertRedirects(response, reverse("tasks:task_list"), fetch_redirect_response=False)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_assignee_cannot_delete_other_persons_task(self):
        self.client.force_login(self.assignee)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.post(self.url(), {"confirm_delete": "yes"}).status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_superuser_can_delete(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url(), {"confirm_delete": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_anonymous_user_cannot_delete(self):
        response = self.client.post(self.url(), {"confirm_delete": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
