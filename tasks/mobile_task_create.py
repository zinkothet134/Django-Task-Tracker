"""Phase 6B.2: explicit, idempotent, PERSONAL task creation from mobile.

No update, delete, assignment, department or organization data is accepted.
"""
import hashlib
import json

from django.db import transaction
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import MobileTaskUploadKey, Task


class MobileCreateThrottle(UserRateThrottle):
    rate = '30/hour'


class MobileCreateSerializer(serializers.Serializer):
    client_task_id = serializers.UUIDField()
    title = serializers.CharField(max_length=200, trim_whitespace=True, allow_blank=False)
    description = serializers.CharField(allow_blank=True, required=False, default='')
    status = serializers.ChoiceField(choices=Task.STATUS_CHOICES)
    priority = serializers.ChoiceField(choices=Task.PRIORITY_CHOICES)
    task_nature = serializers.ChoiceField(choices=Task.TASK_NATURE_CHOICES)
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
    attachment_link = serializers.URLField(required=False, allow_blank=True, allow_null=True, default=None)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([MobileCreateThrottle])
def mobile_create_task(request):
    form = MobileCreateSerializer(data=request.data)
    form.is_valid(raise_exception=True)
    values = form.validated_data
    # Stable digest of accepted, validated fields; repeat with altered payload yields 409.
    digest = hashlib.sha256(json.dumps(form.data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

    with transaction.atomic():
        key, newly_claimed = MobileTaskUploadKey.objects.select_for_update().get_or_create(
            user=request.user,
            client_task_id=values['client_task_id'],
            defaults={'payload_sha256': digest},
        )
        if not newly_claimed:
            if key.payload_sha256 != digest:
                return Response({'detail': 'This local task was previously uploaded with different content. The existing server task was not changed.'}, status=status.HTTP_409_CONFLICT)
            if not key.task_id:
                return Response({'detail': 'The original uploaded task was deleted on the server.'}, status=status.HTTP_410_GONE)
            return Response({'id': key.task_id, 'created': False}, status=status.HTTP_200_OK)

        task = Task.objects.create(
            title=values['title'],
            description=values.get('description', ''),
            status=values['status'],
            priority=values['priority'],
            task_nature=values['task_nature'],
            due_date=values.get('due_date'),
            attachment_link=values.get('attachment_link') or None,
            visibility=Task.PERSONAL,
            created_by=request.user,
            assigned_to=request.user,
        )
        key.task = task
        key.save(update_fields=['task'])
    return Response({'id': task.pk, 'created': True}, status=status.HTTP_201_CREATED)
