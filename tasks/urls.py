from django.urls import path
from . import views
from . import task_delete_views
from . import one_page_report_views
from . import timesheet_views
from . import ai_timesheet_views

app_name = "tasks"

urlpatterns = [
    path("<int:pk>/delete/", task_delete_views.task_delete, name="task_delete"),
    path("reports/one-page/", one_page_report_views.one_page_report, name="one_page_report"),
    path("", views.dashboard, name="dashboard"),
    path("timesheet/", timesheet_views.monthly_timesheet, name="monthly_timesheet"),
    path("timesheet/ai-draft/", ai_timesheet_views.generate_ai_timesheet, name="ai_timesheet_draft"),
    path("timesheet/download/", timesheet_views.download_monthly_timesheet, name="download_monthly_timesheet"),
    path("list/", views.task_list, name="task_list"),
    path("create/", views.task_create, name="task_create"),
    path("<int:pk>/", views.task_detail, name="task_detail"),
    path("<int:pk>/edit/", views.task_update, name="task_update"),
    # Departments
    path("departments/create/", views.department_create, name="department_create"),

    # Profile / Department
    path("profile/department/", views.profile_department_update, name="profile_department_update"),

    # API Endpoints
    path("api/polish-text/", views.polish_text_api, name="polish_text_api"),
]