from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TaskForm, DepartmentForm, ProfileDepartmentForm
from .models import Task, Department, Profile


def _visible_tasks_for_user(user):
    tasks = Task.objects.select_related("assigned_to", "created_by", "department")

    if user.is_superuser:
        return tasks

    user_department = getattr(getattr(user, "profile", None), "department", None)

    visibility_filter = Q(created_by=user) | Q(assigned_to=user)
    if user_department:
        visibility_filter |= Q(department=user_department)

    return tasks.filter(visibility_filter).distinct()


@login_required
def dashboard(request):
    tasks = _visible_tasks_for_user(request.user)

    context = {
        "total_tasks": tasks.count(),
        "todo_count": tasks.filter(status=Task.TODO).count(),
        "progress_count": tasks.filter(status=Task.IN_PROGRESS).count(),
        "done_count": tasks.filter(status=Task.DONE).count(),
        "blocked_count": tasks.filter(status=Task.BLOCKED).count(),
        "my_tasks_count": tasks.filter(assigned_to=request.user).count(),
        "recent_tasks": tasks.order_by("-created_at")[:6],
    }
    return render(request, "tasks/dashboard.html", context)


@login_required
def task_list(request):
    tasks = _visible_tasks_for_user(request.user)

    keyword = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    priority = (request.GET.get("priority") or "").strip()
    assignee = (request.GET.get("assignee") or "").strip()
    department = (request.GET.get("department") or "").strip()
    scope = (request.GET.get("scope") or "all").strip()

    if keyword:
        tasks = tasks.filter(
            Q(title__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(created_by__username__icontains=keyword) |
            Q(assigned_to__username__icontains=keyword) |
            Q(department__name__icontains=keyword)
        )

    if status:
        tasks = tasks.filter(status=status)

    if priority:
        tasks = tasks.filter(priority=priority)

    if department:
        tasks = tasks.filter(department_id=department)

    if assignee == "me":
        tasks = tasks.filter(assigned_to=request.user)

    user_department = getattr(getattr(request.user, "profile", None), "department", None)
    if scope == "department" and user_department:
        tasks = tasks.filter(department=user_department)

    if scope == "created":
        tasks = tasks.filter(created_by=request.user)
    elif scope == "assigned":
        tasks = tasks.filter(assigned_to=request.user)

    context = {
        "tasks": tasks,
        "keyword": keyword,
        "selected_status": status,
        "selected_priority": priority,
        "selected_assignee": assignee,
        "selected_department": department,
        "selected_scope": scope,
        "status_choices": Task.STATUS_CHOICES,
        "priority_choices": Task.PRIORITY_CHOICES,
        "departments": Department.objects.all().order_by("name"),
    }
    return render(request, "tasks/task_list.html", context)


@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if not task.department:
                task.department = getattr(getattr(request.user, "profile", None), "department", None)
            task.save()
            return redirect(task.get_absolute_url())
    else:
        form = TaskForm()

    return render(request, "tasks/task_form.html", {
        "form": form,
        "page_title": "Create Task",
        "button_text": "Create Task",
    })


@login_required
def task_update(request, pk):
    visible_tasks = _visible_tasks_for_user(request.user)
    task = get_object_or_404(visible_tasks, pk=pk)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect(task.get_absolute_url())
    else:
        form = TaskForm(instance=task)

    return render(request, "tasks/task_form.html", {
        "form": form,
        "task": task,
        "page_title": "Edit Task",
        "button_text": "Update Task",
    })


@login_required
def task_detail(request, pk):
    visible_tasks = _visible_tasks_for_user(request.user)
    task = get_object_or_404(visible_tasks, pk=pk)
    return render(request, "tasks/task_detail.html", {"task": task})


@login_required
def department_create(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("tasks:dashboard")
    else:
        form = DepartmentForm()

    return render(request, "tasks/department_form.html", {
        "form": form
    })


@login_required
def profile_department_update(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileDepartmentForm(request.POST)
        if form.is_valid():
            profile.department = form.cleaned_data["department"]
            profile.save()
            return redirect("tasks:dashboard")
    else:
        form = ProfileDepartmentForm(initial={"department": profile.department})

    return render(request, "tasks/profile_department_form.html", {
        "form": form,
        "profile": profile,
    })