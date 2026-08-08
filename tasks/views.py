import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from .forms import TaskForm, DepartmentForm, ProfileDepartmentForm
from .models import Task, Department, Profile
from django.conf import settings
from django.core.mail import send_mail
from openai import OpenAI


def _visible_tasks_for_user(user):
    tasks = Task.objects.select_related("assigned_to", "created_by", "department")

    if user.is_superuser:
        return tasks

    profile = getattr(user, "profile", None)
    user_department = getattr(profile, "department", None)
    user_organization_id = (getattr(profile, "organization_id", "") or "").strip()

    visibility_filter = Q(created_by=user) | Q(assigned_to=user)

    if user_organization_id:
        visibility_filter |= Q(
            organization_id=user_organization_id,
            visibility=Task.ORGANIZATION,
        )

        if user_department:
            visibility_filter |= Q(
                organization_id=user_organization_id,
                department=user_department,
                visibility=Task.DEPARTMENT,
            )

    return tasks.filter(visibility_filter).distinct()


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)

    if profile and getattr(profile, "app_purpose", "PERSONAL") == "TEAM" and not getattr(profile, "department", None):
        user_organization_id = (getattr(profile, "organization_id", "") or "").strip()
        has_available_departments = Department.objects.filter(
            organization_id=user_organization_id
        ).exists()

        if has_available_departments:
            return redirect("tasks:profile_department_update")

    tasks = _visible_tasks_for_user(request.user)
    priority_summary = tasks.filter(status__in=[Task.TODO, Task.IN_PROGRESS]).values("priority").annotate(total=Count("id")).order_by("priority")
    priority_choices = dict(Task.PRIORITY_CHOICES)


    context = {
        "total_tasks": tasks.count(),
        "todo_count": tasks.filter(status=Task.TODO).count(),
        "progress_count": tasks.filter(status=Task.IN_PROGRESS).count(),
        "done_count": tasks.filter(status=Task.DONE).count(),
        "blocked_count": tasks.filter(status=Task.BLOCKED).count(),
        "my_tasks_count": tasks.filter(assigned_to=request.user).count(),
        "recent_tasks": tasks.order_by("-created_at")[:6],
        "status_todo": Task.TODO,
        "status_in_progress": Task.IN_PROGRESS,
        "status_done": Task.DONE,
        "status_blocked": Task.BLOCKED,
        "referral_code": getattr(profile, "organization_referral_code", "") if getattr(profile, "app_purpose", "PERSONAL") == "TEAM" else "",
        "show_referral_code": getattr(profile, "app_purpose", "PERSONAL") == "TEAM" and bool(getattr(profile, "organization_referral_code", "")),
        "status_chart_labels": ["To Do", "In Progress", "Done", "Blocked"],
        "status_chart_data": [
            tasks.filter(status=Task.TODO).count(),
            tasks.filter(status=Task.IN_PROGRESS).count(),
            tasks.filter(status=Task.DONE).count(),
            tasks.filter(status=Task.BLOCKED).count(),
        ],
        "priority_chart_title": "Tasks by Priority (To Do + In Progress)",
        "priority_chart_labels": [priority_choices.get(item["priority"], item["priority"]) for item in priority_summary],
        "priority_chart_data": [item["total"] for item in priority_summary],
    }
    return render(request, "tasks/dashboard.html", context)


@login_required
def task_list(request):
    tasks = _visible_tasks_for_user(request.user)

    keyword = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    status_aliases = {
        "progress": Task.IN_PROGRESS,
        "in-progress": Task.IN_PROGRESS,
        "in_progress": Task.IN_PROGRESS,
        "todo": Task.TODO,
        "done": Task.DONE,
        "blocked": Task.BLOCKED,
    }
    status = status_aliases.get(status.lower(), status)
    priority = (request.GET.get("priority") or "").strip()
    assignee = (request.GET.get("assignee") or request.GET.get("assigned") or "").strip()
    department = (request.GET.get("department") or "").strip()
    scope = (request.GET.get("scope") or "all").strip()

    if keyword:
        tasks = tasks.filter(
            Q(title__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(attachment_link__icontains=keyword) |
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

    profile = getattr(request.user, "profile", None)
    user_department = getattr(profile, "department", None)
    user_organization_id = (getattr(profile, "organization_id", "") or "").strip()

    if scope == "department":
        if user_department and user_organization_id:
            tasks = tasks.filter(
                organization_id=user_organization_id,
                department=user_department,
                visibility=Task.DEPARTMENT,
            )
        else:
            tasks = tasks.none()

    if scope == "organization":
        if user_organization_id:
            tasks = tasks.filter(
                organization_id=user_organization_id,
                visibility=Task.ORGANIZATION,
            )
        else:
            tasks = tasks.none()

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
        "departments": Department.objects.filter(organization_id=user_organization_id).order_by("name") if user_organization_id else Department.objects.none(),
    }
    return render(request, "tasks/task_list.html", context)


@login_required
def task_create(request):
    profile = getattr(request.user, "profile", None)
    is_personal_user = getattr(profile, "app_purpose", "PERSONAL") == "PERSONAL"

    if request.method == "POST":
        form = TaskForm(request.POST, user=request.user) if is_personal_user else TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            user_department = getattr(profile, "department", None)
            user_organization_id = (getattr(profile, "organization_id", "") or "").strip()

            if not getattr(task, "department", None):
                task.department = user_department

            if user_organization_id:
                task.organization_id = user_organization_id
                if task.department:
                    task.visibility = Task.DEPARTMENT
                else:
                    task.visibility = Task.ORGANIZATION if getattr(profile, "app_purpose", "PERSONAL") == "TEAM" else Task.PERSONAL
            else:
                task.visibility = Task.PERSONAL

            if is_personal_user and hasattr(task, "assigned_to") and not task.assigned_to:
                task.assigned_to = request.user

            task.save()
            send_task_mail(task)
            return redirect(task.get_absolute_url())
    else:
        form = TaskForm(user=request.user) if is_personal_user else TaskForm()

    return render(request, "tasks/task_form.html", {
        "form": form,
        "page_title": "Create Task",
        "button_text": "Create Task",
    })


@login_required
def task_update(request, pk):
    visible_tasks = _visible_tasks_for_user(request.user)
    task = get_object_or_404(visible_tasks, pk=pk)
    profile = getattr(request.user, "profile", None)
    is_personal_user = getattr(profile, "app_purpose", "PERSONAL") == "PERSONAL"

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, user=request.user) if is_personal_user else TaskForm(request.POST, instance=task)
        if form.is_valid():
            updated_task = form.save(commit=False)
            if is_personal_user and hasattr(updated_task, "assigned_to") and not updated_task.assigned_to:
                updated_task.assigned_to = request.user
            updated_task.save()
            return redirect(updated_task.get_absolute_url())
    else:
        form = TaskForm(instance=task, user=request.user) if is_personal_user else TaskForm(instance=task)

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
            department = form.save(commit=False)
            profile = getattr(request.user, "profile", None)
            department.organization_id = (getattr(profile, "organization_id", "") or "").strip()
            department.save()
            return redirect("tasks:dashboard")
    else:
        form = DepartmentForm()

    return render(request, "tasks/department_form.html", {
        "form": form
    })


@login_required
def profile_department_update(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    user_organization_id = (getattr(profile, "organization_id", "") or "").strip()
    allowed_departments = Department.objects.filter(organization_id=user_organization_id).order_by("name") if user_organization_id else Department.objects.none()

    if request.method == "POST":
        form = ProfileDepartmentForm(request.POST)
        form.fields["department"].queryset = allowed_departments
        if form.is_valid():
            profile.department = form.cleaned_data["department"]
            profile.save()
            return redirect("tasks:dashboard")
    else:
        form = ProfileDepartmentForm(initial={"department": profile.department})
        form.fields["department"].queryset = allowed_departments

    return render(request, "tasks/profile_department_form.html", {
        "form": form,
        "profile": profile,
    })


def send_task_mail(task):
    if task.assigned_to and task.assigned_to.email:
        send_mail(
            subject=f"New Task Assigned: {task.title}",
            message=f"""Hello {task.assigned_to.get_full_name() or task.assigned_to.username},
You have been assigned a task. 
Title: {task.title}
Due Date: {task.due_date}

View Task: 
http://chuefamily.shop{task.get_absolute_url()}

Thank you, 
ChueFamily
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[task.assigned_to.email],
            fail_silently=False,
        )

@login_required
@require_POST
def polish_text_api(request):
    try:
        data = json.loads(request.body)
        raw_text = data.get('text', '').strip()
        action = data.get('action', 'polish')  # Default to polish if missing

        if not raw_text:
            return JsonResponse({'error': 'No text provided'}, status=400)

        # Dynamically set the system instruction based on user choice
        if action == 'burmese':
            system_prompt = "You are a professional translator. Translate the provided task description accurately into natural Burmese. Return ONLY the translated text."
        elif action == 'concise':
            system_prompt = "You are a professional editor. Rewrite the following task description to be extremely short and punchy. Return ONLY the revised text."
        else: # default 'polish'
            system_prompt = "You are a professional editor. Correct any grammar mistakes and polish the provided task text to be clear, professional, and concise. Return ONLY the polished text."

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text}
            ],
            temperature=0.3,
            max_tokens=500
        )

        polished_text = response.choices[0].message.content.strip()
        return JsonResponse({'polished_text': polished_text})

    except Exception as e:
        print(f"🔥 AI API ERROR: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)