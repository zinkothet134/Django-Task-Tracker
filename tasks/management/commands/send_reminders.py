import time
from django.core.management.base import BaseCommand
from django.utils.timezone import now, timedelta
from django.core.mail import send_mail
from django.conf import settings
from tasks.models import Task

class Command(BaseCommand):
    help = "Run a continuous loop to send task reminders once per day"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("🚀 Starting Continuous Reminder Service..."))

        while True:
            current_time = now()
            # logic: Only send reminders once a day (e.g., at 9:00 AM)
            # Or simply run the check every 12 hours.
            
            self.stdout.write(f"[{current_time}] Checking for tasks due tomorrow...")
            
            tomorrow = current_time.date() + timedelta(days=1)
            tasks = Task.objects.filter(
                due_date=tomorrow,
                status__in=[Task.TODO, Task.IN_PROGRESS]
            )

            sent_count = 0
            for task in tasks:
                if task.assigned_to and task.assigned_to.email:
                    try:
                        send_mail(
                            subject=f"Reminder: Task due tomorrow - {task.title}",
                            message=f"""Hello {task.assigned_to.get_full_name() or task.assigned_to.username},

Reminder: Your task is due tomorrow.

Title: {task.title}
Due Date: {task.due_date}

Please complete it on time.

View Task:
{settings.SITE_URL}{task.get_absolute_url()}

— Chue Family""",
                            from_email=f"Chue Family <{settings.DEFAULT_FROM_EMAIL}>",
                            recipient_list=[task.assigned_to.email],
                            fail_silently=False,
                        )
                        sent_count += 1
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f"Failed for task {task.id}: {e}"))

            self.stdout.write(self.style.SUCCESS(f"Finished check. Sent: {sent_count}"))
            
            # --- THE LOOP CONTROL ---
            # Sleep for 12 hours (43,200 seconds) before checking again
            # This prevents your CPU usage from spiking on Seenode.
            self.stdout.write("Sleeping for 12 hours...")
            time.sleep(43200)