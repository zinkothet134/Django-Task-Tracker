from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone

# Create your models here.
class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    organization_id = models.CharField(max_length=100, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'organization_id'],
                name='unique_department_name_per_organization'
                )
        ]

    def __str__(self):
        return self.name
    
class Task(models.Model):
    TODO =  'TODO'
    IN_PROGRESS = 'IN_PROGRESS'
    DONE = 'DONE'
    BLOCKED = 'BLOCKED'

    STATUS_CHOICES = (
        (TODO, 'To Do'),
        (IN_PROGRESS, 'In Progress'),
        (DONE, 'Done'),
        (BLOCKED, 'Blocked'),
    )

    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    URGENT = 'URGENT'

    PRIORITY_CHOICES = (
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
        (URGENT, "Urgent"),
    )

    PERSONAL = 'PERSONAL'
    DEPARTMENT = 'DEPARTMENT'
    ORGANIZATION = 'ORGANIZATION'

    VISIBILITY_CHOICES = (
        (PERSONAL, 'Personal'),
        (DEPARTMENT, 'Department'),
        (ORGANIZATION, 'Organization'),
    )

    ORDINARY = 'ORDINARY'
    UNFINISHED_WORK = 'UNFINISHED_WORK'

    TASK_NATURE_CHOICES = (
        (ORDINARY, 'Oridinary Task'),
        (UNFINISHED_WORK, 'Unfinished Work')
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=TODO)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    attachment_link = models.URLField(null=True, blank=True, help_text='Optional link to Google Drive, OneDrive, or any external resource')
    organization_id = models.CharField(max_length=100, blank=True, db_index=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=PERSONAL)
    task_nature = models.CharField(max_length=30, choices=TASK_NATURE_CHOICES, default=ORDINARY)

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('tasks:task_detail', args=[self.pk])
    


# New Profile model
class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    APP_PURPOSE_CHOICES = (
        ('PERSONAL', 'Personal Productivity'),
        ('TEAM', 'Organization Team Coordination'),
    )

    app_purpose = models.CharField(max_length=20, choices=APP_PURPOSE_CHOICES, default='PERSONAL')
    organization_id = models.CharField(max_length=100, blank=True, db_index=True)
    staff_id = models.CharField(max_length=100, blank=True)
    organization_referral_code = models.CharField(max_length=120, blank=True, db_index=True)
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_users",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    image = models.ImageField(upload_to="profiles/", null=True, blank=True)
    is_premium = models.BooleanField(default=False)
    subscription_expiry = models.DateTimeField(blank=True, null=True)

    @property
    def has_active_subscription(self):
        """Checks if the user has an active, non-expired subscription."""
        if self.is_premium:
            if self.subscription_expiry:
                return self.subscription_expiry > timezone.now()
            # If is_premium is True but no expiry date is set, treat it as active (or lifetime)
            return True
        return False

    def save(self, *args, **kwargs):
        if self.organization_id and not self.organization_referral_code:
            base_code = slugify(self.organization_id).replace("-", "").upper()[:24] or "ORG"
            candidate = base_code
            counter = 1
            while Profile.objects.exclude(pk=self.pk).filter(organization_referral_code=candidate).exists():
                counter += 1
                candidate = f"{base_code}{counter}"
            self.organization_referral_code = candidate
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.user.username} Profile"
