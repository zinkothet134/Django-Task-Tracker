"""
URL configuration for task_tracker_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from tasks.mobile_api import MobileTokenObtainPairView, mobile_me, mobile_tasks
from rest_framework_simplejwt.views import TokenRefreshView

from tasks.mobile_task_create import mobile_create_task

from tasks.mobile_task_update import mobile_update_task

urlpatterns = [
    path("api/mobile/tasks/<int:task_id>/update/", mobile_update_task, name="mobile_task_update"),
    path("api/mobile/tasks/create/", mobile_create_task, name="mobile_task_create"),
    path("api/mobile/login/", MobileTokenObtainPairView.as_view(), name="mobile_login"),
    path("api/mobile/token/refresh/", TokenRefreshView.as_view(), name="mobile_token_refresh"),
    path("api/mobile/me/", mobile_me, name="mobile_me"),
    path("api/mobile/tasks/", mobile_tasks, name="mobile_tasks"),
    path("", RedirectView.as_view(url="/tasks/", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("tasks/", include("tasks.urls")),
]
