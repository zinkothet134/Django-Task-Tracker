from django.contrib import admin
from .models import Task, Department
# Register your models here.

admin.site.register(Department)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "priority",
        "assigned_to",
        "created_by",
        "due_date",
        "created_at",
    )
    list_filter = ("status", "priority", "due_date")
    search_fields = ("title", "description", "assigned_to__username", "created_by__username")

