"""Phase 6B.4: JWT authenticated, optimistic-concurrency edits of existing Django tasks.

The endpoint accepts only title, description, status and priority. No changes to
ownership, team visibility, assignments or deletion. Stale edits return 409.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Task
from .views import _visible_tasks_for_user


class MobileUpdateThrottle(UserRateThrottle):
    rate = '60/hour'


class MobileTaskUpdateSerializer(serializers.Serializer):
    base_updated_at = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=200, trim_whitespace=True, allow_blank=False)
    description = serializers.CharField(allow_blank=True, required=False, default='')
    status = serializers.ChoiceField(choices=Task.STATUS_CHOICES)
    priority = serializers.ChoiceField(choices=Task.PRIORITY_CHOICES)

    def to_internal_value(self, data):
        unexpected = set(data.keys()) - {'base_updated_at', 'title', 'description', 'status', 'priority'}
        if unexpected:
            raise serializers.ValidationError({'detail': 'Unsupported fields: ' + ', '.join(sorted(unexpected))})
        return super().to_internal_value(data)

    def validate_base_updated_at(self, value):
        instant = parse_datetime(value)
        if instant is None or not timezone.is_aware(instant):
            raise serializers.ValidationError('An ISO 8601 timezone-aware updated_at value is required.')
        return instant


def _task_data(task):
    return {
        'id': task.pk,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'priority': task.priority,
        'task_nature': task.task_nature,
        'visibility': task.visibility,
        'organization_id': task.organization_id,
        'department_id': task.department_id,
        'created_by_id': task.created_by_id,
        'assigned_to_id': task.assigned_to_id,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'attachment_link': task.attachment_link,
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat(),
    }


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([MobileUpdateThrottle])
def mobile_update_task(request, task_id):
    form = MobileTaskUpdateSerializer(data=request.data)
    form.is_valid(raise_exception=True)

    with transaction.atomic():
        # Lock the *base* row, not a distinct() or join-rich visibility query.
        task = Task.objects.select_for_update().filter(pk=task_id).first()
        if task is None or not _visible_tasks_for_user(request.user).filter(pk=task.pk).exists():
            return Response({'detail': 'Task not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Read permission is broader than write permission. Team/organization
        # bystanders cannot edit a task simply because it is visible to them.
        if not (request.user.is_superuser or
                task.created_by_id == request.user.pk or
                task.assigned_to_id == request.user.pk):
            return Response({'detail': 'Only the creator or assignee can edit this task from mobile.'},
                            status=status.HTTP_403_FORBIDDEN)

        if form.validated_data['base_updated_at'] != task.updated_at:
            return Response({
                'detail': 'The task was changed on the server since your offline copy was downloaded. Your mobile draft was not applied.',
                'server_task': _task_data(task),
            }, status=status.HTTP_409_CONFLICT)

        for field in ('title', 'description', 'status', 'priority'):
            setattr(task, field, form.validated_data[field])
        task.save(update_fields=['title', 'description', 'status', 'priority', 'updated_at'])
        return Response({'task': _task_data(task)}, status=status.HTTP_200_OK)
