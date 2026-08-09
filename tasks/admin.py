from django.contrib import admin
from .models import Task, Department, Profile
# Register your models here.

admin.site.register(Department)
# admin.site.register(Profile)
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'app_purpose', 'organization_id', 'is_premium', 'subscription_expiry')
    list_filter = ('is_premium', 'app_purpose')
    search_fields = ('user__email', 'organization_id', 'staff_id')

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

