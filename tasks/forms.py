from django import forms
from .models import Task, Department, Profile


class TaskForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "attachment_link",
            "department",
            "assigned_to",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Task title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Task description",
                }
            ),
            "attachment_link": forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'https://drive.google.com/... or https://onedrive.live.com/...',
                }
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
        }
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user:
            profile = getattr(user, "profile", None)

            # PERSONAL user → hide org-related fields
            if profile and getattr(profile, "app_purpose", "PERSONAL") == "PERSONAL":
                self.fields.pop("department", None)
                self.fields.pop("assigned_to", None)

            # TEAM user → restrict choices properly
            elif profile and getattr(profile, "app_purpose", "PERSONAL") == "TEAM":
                user_org = (getattr(profile, "organization_id", "") or "").strip()

                if "department" in self.fields:
                    self.fields["department"].queryset = Department.objects.filter(
                        organization_id=user_org
                    ).order_by("name")

                if "assigned_to" in self.fields:
                    self.fields["assigned_to"].queryset = (
                        Profile.objects.filter(
                            organization_id=user_org
                        )
                        .select_related("user")
                        .order_by("user__username")
                        .values_list("user", flat=True)
                    )
                if "assigned_to" in self.fields:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()

                    self.fields["assigned_to"].queryset = User.objects.filter(
                        profile__organization_id=user_org
                    ).order_by("username")

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Department name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Optional description",
                }
            ),
        }

class ProfileDepartmentForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )


class OrganizationSignupForm(forms.Form):
    organization_referral_code = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter organization referral code if you were invited",
            }
        ),
    )
    app_purpose = forms.ChoiceField(
        choices=Profile.APP_PURPOSE_CHOICES,
        initial="PERSONAL",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    organization_id = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter organization ID if using this app for team coordination",
            }
        ),
    )
    department_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Create your first department for this organization",
            }
        ),
    )
    staff_id = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your staff ID if applicable",
            }
        ),
    )

    def clean(self):
        cleaned_data = getattr(super(), "clean", lambda: {})()
        app_purpose = (cleaned_data.get("app_purpose") or "PERSONAL").strip()
        organization_id = (cleaned_data.get("organization_id") or "").strip()
        
        organization_referral_code = (cleaned_data.get("organization_referral_code") or "").strip().upper()
        staff_id = (cleaned_data.get("staff_id") or "").strip()
        department_name = (cleaned_data.get("department_name") or "").strip()

        referred_profile = None
        if organization_referral_code:
            referred_profile = Profile.objects.filter(
                organization_referral_code=organization_referral_code
            ).select_related("user").first()
            if not referred_profile:
                self.add_error("organization_referral_code", "Referral code was not found.")
            else:
                cleaned_data["organization_id"] = referred_profile.organization_id
                organization_id = referred_profile.organization_id
                cleaned_data["referred_profile"] = referred_profile

        if app_purpose == "TEAM":
            if not organization_id and not organization_referral_code:
                self.add_error("organization_id", "Organization ID or referral code is required for team coordination accounts.")
            if not staff_id:
                self.add_error("staff_id", "Staff ID is required for team coordination accounts.")
            if not organization_referral_code and not department_name:
                self.add_error("department_name", "Department is required when creating a new organization team account.")

        return cleaned_data

    def signup(self, request, user):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.app_purpose = self.cleaned_data.get("app_purpose") or "PERSONAL"
        profile.organization_id = (self.cleaned_data.get("organization_id") or "").strip()

        referred_profile = self.cleaned_data.get("referred_profile")
        if referred_profile:
            profile.referred_by = referred_profile.user

        profile.staff_id = (self.cleaned_data.get("staff_id") or "").strip()
        profile.save()

        department_name = (self.cleaned_data.get("department_name") or "").strip()

        if profile.app_purpose == "TEAM":
            if department_name and profile.organization_id:
                department, _ = Department.objects.get_or_create(
                    name=department_name,
                    organization_id=profile.organization_id,
                    defaults={"description": ""},
                )
                profile.department = department

            elif referred_profile and referred_profile.department:
                profile.department = referred_profile.department

            profile.save(update_fields=["department"])