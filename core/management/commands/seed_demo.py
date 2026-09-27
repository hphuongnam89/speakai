import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Course, CourseTeachingAssignment, Enrollment


DEMO_USERS = (
    ("demo-student", "student", "DEMO_STUDENT_PASSWORD"),
    ("demo-teacher", "teacher", "DEMO_TEACHER_PASSWORD"),
    ("demo-admin", "admin", "DEMO_ADMIN_PASSWORD"),
)
ROLE_NAMES = {role for _, role, _ in DEMO_USERS}


class Command(BaseCommand):
    help = "Create or refresh synthetic demo accounts and role groups."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        prepared = []
        errors = []

        for username, role, password_env in DEMO_USERS:
            password = os.getenv(password_env, "")
            if not password or password.startswith("replace-"):
                errors.append(f"{password_env} must be set to a local password")
                continue
            try:
                validate_password(password, user=User(username=username))
            except ValidationError as exc:
                errors.extend(f"{password_env}: {message}" for message in exc.messages)
                continue
            prepared.append((username, role, password))

        if errors:
            raise CommandError("Invalid demo password configuration: " + "; ".join(errors))

        for username, role, password in prepared:
            email = f"{username}@example.test"
            user = User.objects.filter(username=username).first()
            if user and (user.is_staff or user.is_superuser):
                raise CommandError(f"Refusing to modify privileged account '{username}'")
            if user and user.email != email:
                raise CommandError(f"Refusing to modify existing account '{username}'")
            if user and user.groups.filter(name__in=ROLE_NAMES).exclude(name=role).exists():
                raise CommandError(f"Refusing to change the role of existing account '{username}'")
            if user is None:
                user = User.objects.create_user(username=username, email=email, password=password)
            else:
                user.set_password(password)
                user.save(update_fields=["password"])
            user.groups.add(Group.objects.get_or_create(name=role)[0])

        student = User.objects.get(username="demo-student")
        teacher = User.objects.get(username="demo-teacher")
        course, _ = Course.objects.get_or_create(
            code="GT1", defaults={
                "name": "Giao tiếp 1", "description": "Học phần demo luyện nói bằng AI; không phải cấu hình thi chính thức.",
            },
        )
        Enrollment.objects.get_or_create(student=student, course=course)
        CourseTeachingAssignment.objects.get_or_create(teacher=teacher, course=course)

        self.stdout.write(self.style.SUCCESS("Demo accounts are ready: demo-student, demo-teacher, demo-admin."))
