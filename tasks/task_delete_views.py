"""TaskFlow task deletion: creator or superuser only, confirmed POST only.

We keep this view separate from views.py so existing AI/report code is untouched.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import Task


@login_required
@require_http_methods(["GET", "POST"])
def task_delete(request, pk):
    """GET displays a confirmation; POST with explicit consent deletes a task.

    A task's assignee or someone viewing an organization-wide task does not
    automatically gain permission to delete it.
    """
    allowed = Task.objects.select_related("created_by", "assigned_to")
    if not request.user.is_superuser:
        allowed = allowed.filter(created_by=request.user)
    task = get_object_or_404(allowed, pk=pk)

    if request.method == "POST":
        if request.POST.get("confirm_delete") != "yes":
            return render(
                request,
                "tasks/task_confirm_delete.html",
                {"task": task, "error": "Tick the confirmation checkbox to delete this task."},
                status=400,
            )

        title = task.title
        task.delete()
        messages.success(request, f'Task "{title}" was permanently deleted.')
        return redirect("tasks:task_list")

    return render(request, "tasks/task_confirm_delete.html", {"task": task})
