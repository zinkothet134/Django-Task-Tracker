from django.urls import path
from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("list/", views.task_list, name="task_list"),
    path("create/", views.task_create, name="task_create"),
    path("<int:pk>/", views.task_detail, name="task_detail"),
    path("<int:pk>/edit/", views.task_update, name="task_update"),
    # Departments
    path("departments/create/", views.department_create, name="department_create"),

    # Profile / Department
    path("profile/department/", views.profile_department_update, name="profile_department_update"),
]