"""TaskFlow Phase 6A: authenticated, read-only mobile endpoints.

Do not add write methods until offline task ownership and conflict handling exist.
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .views import _visible_tasks_for_user


class MobileLoginSerializer(TokenObtainPairSerializer):
    """Accept a username OR verified-unique email as the login identifier."""

    def validate(self, attrs):
        identifier = (attrs.get(self.username_field) or "").strip()
        if "@" in identifier:
            User = get_user_model()
            users = list(User._default_manager.filter(email__iexact=identifier).only(User.USERNAME_FIELD)[:2])
            if len(users) == 1:
                attrs[self.username_field] = getattr(users[0], User.USERNAME_FIELD)
        result = super().validate(attrs)
        # Apply the same existing account-email verification rule when an
        # allauth EmailAddress object is present. Superusers may be manually made.
        if not self.user.is_superuser:
            from allauth.account.models import EmailAddress
            addresses = EmailAddress.objects.filter(user=self.user)
            if addresses.exists() and not addresses.filter(verified=True).exists():
                raise serializers.ValidationError("Verify your email before signing in on mobile.")
        return result


class MobileLoginThrottle(AnonRateThrottle):
    rate = '5/minute'


class MobileTokenObtainPairView(TokenObtainPairView):
    serializer_class = MobileLoginSerializer
    throttle_classes = [MobileLoginThrottle]


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def mobile_me(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    return Response({
        'id': user.pk,
        'username': user.get_username(),
        'email': user.email,
        'display_name': user.get_full_name() or user.get_username(),
        'organization_id': getattr(profile, 'organization_id', '') if profile else '',
    })


class MobileTaskPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def mobile_tasks(request):
    # Critical: use the SAME visibility rules as the web dashboard.
    queryset = _visible_tasks_for_user(request.user).order_by('-updated_at', '-pk')
    paginator = MobileTaskPagination()
    page = paginator.paginate_queryset(queryset, request)
    data = [{
        'id': t.pk,
        'title': t.title,
        'description': t.description,
        'status': t.status,
        'priority': t.priority,
        'task_nature': t.task_nature,
        'visibility': t.visibility,
        'organization_id': t.organization_id,
        'department_id': t.department_id,
        'created_by_id': t.created_by_id,
        'assigned_to_id': t.assigned_to_id,
        'due_date': t.due_date.isoformat() if t.due_date else None,
        'attachment_link': t.attachment_link,
        'created_at': t.created_at.isoformat(),
        'updated_at': t.updated_at.isoformat(),
    } for t in page]
    return paginator.get_paginated_response(data)
