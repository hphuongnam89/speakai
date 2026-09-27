import os
import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import (
    Course, CourseTeachingAssignment, Enrollment, Question, QuestionReview, QuestionTag, QuestionVersion,
    BlueprintSlot, BlueprintVersion, CriterionLevelDescriptor, Enrollment, ExamBlueprint, ExamAnswer, ExamAttempt,
    PracticeAnswer, PracticeAttempt, Rubric, RubricAuditEvent, RubricCriterion, RubricVersion,
)
from core.blueprints import InsufficientQuestionPool, sample_blueprint
from core.official_scoring import score_official_attempt


class PublicPageTests(TestCase):
    def test_home_page_shows_confirmed_course_levels(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Giao tiếp 1")
        self.assertContains(response, "A1–A2")
        self.assertContains(response, "Chờ tài liệu môn")
        self.assertEqual(response["Content-Security-Policy"].split(";")[0], "default-src 'self'")

    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readiness_checks_database(self):
        response = self.client.get(reverse("health_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready", "database": "ok"})

    @patch("core.views.connection.cursor", side_effect=DatabaseError("private backend detail"))
    def test_readiness_hides_database_error(self, _cursor):
        response = self.client.get(reverse("health_ready"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready"})


class AuthenticationSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_group = Group.objects.create(name="student")
        cls.teacher_group = Group.objects.create(name="teacher")
        cls.admin_group = Group.objects.create(name="admin")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_student_dashboard_and_cross_role_denial(self):
        user = get_user_model().objects.create_user(username="demo-student", password="a-long-demo-password")
        user.groups.add(self.student_group)
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("dashboard_student"))
        response = self.client.get(reverse("dashboard_student"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chưa được ghi danh")
        self.assertNotContains(response, "Giao tiếp 1")
        self.assertNotContains(response, "Quản trị tổng quan")
        self.assertEqual(self.client.get(reverse("dashboard_teacher")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard_admin")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_teacher_dashboard_and_cross_role_denial(self):
        user = get_user_model().objects.create_user(username="demo-teacher", password="a-long-demo-password")
        user.groups.add(self.teacher_group)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("dashboard_teacher"))
        self.assertContains(self.client.get(reverse("dashboard_teacher")), "Khu vực giảng viên")
        self.assertEqual(self.client.get(reverse("dashboard_student")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard_admin")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_admin_group_gets_admin_shell_but_not_django_admin_without_staff(self):
        user = get_user_model().objects.create_user(username="demo-admin", password="a-long-demo-password")
        user.groups.add(self.admin_group)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("dashboard_admin"))
        self.assertContains(self.client.get(reverse("dashboard_admin")), "Tổng quan quản trị")
        self.assertEqual(self.client.get(reverse("dashboard_student")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard_teacher")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_unassigned_user_is_denied_and_superuser_is_admin(self):
        user = get_user_model().objects.create_user(username="unassigned", password="a-long-demo-password")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

        admin = get_user_model().objects.create_superuser(
            username="root-demo", email="root@example.test", password="a-long-demo-password"
        )
        self.client.force_login(admin)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("dashboard_admin"))
        self.assertEqual(self.client.get(reverse("dashboard_admin")).status_code, 200)

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)


class DemoSeedCommandTests(TestCase):
    @patch.dict(os.environ, {
        "DEMO_STUDENT_PASSWORD": "Cedar!8146NorthRiver",
        "DEMO_TEACHER_PASSWORD": "Tidal#2957MangoStone",
        "DEMO_ADMIN_PASSWORD": "Velvet$6402Quartz",
    })
    def test_seed_is_idempotent_and_does_not_grant_staff(self):
        call_command("seed_demo")
        call_command("seed_demo")

        User = get_user_model()
        self.assertEqual(User.objects.filter(username__startswith="demo-").count(), 3)
        for username, role in (
            ("demo-student", "student"),
            ("demo-teacher", "teacher"),
            ("demo-admin", "admin"),
        ):
            user = User.objects.get(username=username)
            self.assertTrue(user.groups.filter(name=role).exists())
            self.assertFalse(user.is_staff)
        self.assertTrue(User.objects.get(username="demo-student").check_password("Cedar!8146NorthRiver"))

    @patch.dict(os.environ, {
        "DEMO_STUDENT_PASSWORD": "replace-with-a-placeholder",
        "DEMO_TEACHER_PASSWORD": "Tidal#2957MangoStone",
        "DEMO_ADMIN_PASSWORD": "Velvet$6402Quartz",
    })
    def test_seed_rejects_placeholder_passwords_without_creating_users(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo")
        self.assertFalse(get_user_model().objects.filter(username__startswith="demo-").exists())

    @patch.dict(os.environ, {
        "DEMO_STUDENT_PASSWORD": "Cedar!8146NorthRiver",
        "DEMO_TEACHER_PASSWORD": "Tidal#2957MangoStone",
        "DEMO_ADMIN_PASSWORD": "Velvet$6402Quartz",
    })
    def test_seed_refuses_to_modify_privileged_demo_account(self):
        User = get_user_model()
        privileged = User.objects.create_superuser(
            username="demo-admin", email="demo-admin@example.test", password="unchanged-demo-pass"
        )
        with self.assertRaises(CommandError):
            call_command("seed_demo")
        privileged.refresh_from_db()
        self.assertTrue(privileged.check_password("unchanged-demo-pass"))
        self.assertFalse(User.objects.filter(username="demo-student").exists())

    @patch.dict(os.environ, {
        "DEMO_STUDENT_PASSWORD": "Cedar!8146NorthRiver",
        "DEMO_TEACHER_PASSWORD": "Tidal#2957MangoStone",
        "DEMO_ADMIN_PASSWORD": "Velvet$6402Quartz",
    })
    def test_seed_refuses_role_conflicts(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="demo-student", email="demo-student@example.test", password="unchanged-demo-pass"
        )
        user.groups.add(Group.objects.create(name="teacher"))
        with self.assertRaises(CommandError):
            call_command("seed_demo")
        user.refresh_from_db()
        self.assertTrue(user.check_password("unchanged-demo-pass"))
        self.assertTrue(user.groups.filter(name="teacher").exists())
        self.assertFalse(User.objects.filter(username="demo-teacher").exists())


class QuestionDomainModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.author = User.objects.create_user(username="question-author", password="demo-password-8146")
        cls.reviewer = User.objects.create_user(username="question-reviewer", password="demo-password-2957")
        cls.course = Course.objects.create(code="GT1", name="Giao tiếp 1")
        cls.question = Question.objects.create(course=cls.course, created_by=cls.author)

    def make_version(self, version=1, **overrides):
        values = {
            "question": self.question,
            "version": version,
            "created_by": self.author,
            "task_type": "",
            "topic": "",
            "prompt_text": "",
        }
        values.update(overrides)
        return QuestionVersion.objects.create(**values)

    def test_enrollment_and_question_version_numbers_are_unique(self):
        Enrollment.objects.create(student=self.author, course=self.course)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(student=self.author, course=self.course)

        self.make_version(task_type="short_response", topic="daily_life", prompt_text="Prompt A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_version(task_type="short_response", topic="daily_life", prompt_text="Prompt B")

    def test_versions_keep_separate_content_and_topic_tags(self):
        first = self.make_version(task_type="short_response", topic="daily_life", prompt_text="Version one")
        second = self.make_version(
            version=2, task_type="short_response", topic="daily_life", prompt_text="Version two"
        )
        tag = QuestionTag.objects.create(name="Daily life", slug="daily-life")
        first.tags.add(tag)

        self.assertEqual(list(self.question.versions.values_list("version", flat=True)), [1, 2])
        self.assertEqual(first.prompt_text, "Version one")
        self.assertEqual(second.prompt_text, "Version two")
        self.assertQuerySetEqual(first.tags.all(), [tag])
        self.assertEqual(second.status, QuestionVersion.Status.DRAFT)

    def test_level_range_validation_and_positive_version_constraint(self):
        version = QuestionVersion(
            question=self.question,
            version=1,
            created_by=self.author,
            task_type="short_response",
            topic="daily_life",
            prompt_text="Prompt",
            target_level_min="B2",
            target_level_max="A2",
        )
        with self.assertRaises(ValidationError):
            version.full_clean()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_version(version=0, task_type="short_response", topic="daily_life", prompt_text="Prompt")

    def test_review_cannot_be_authored_by_question_version_author(self):
        version = self.make_version(task_type="short_response", topic="daily_life", prompt_text="Prompt")
        review = QuestionReview(
            question_version=version,
            reviewer=self.author,
            decision=QuestionReview.Decision.APPROVED,
        )
        with self.assertRaises(ValidationError):
            review.full_clean()
        review.reviewer = self.reviewer
        review.full_clean()
        review.save()
        with self.assertRaises(ProtectedError):
            version.delete()

    def test_course_delete_preserves_enrollment_and_question_history(self):
        Enrollment.objects.create(student=self.author, course=self.course)
        with self.assertRaises(ProtectedError):
            self.course.delete()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_locked_version_content_and_tags_cannot_be_changed(self):
        version = self.make_version(task_type="solo", topic="daily_life", prompt_text="Prompt")
        version.status = QuestionVersion.Status.IN_REVIEW
        version.save()
        version.prompt_text = "Edited"
        with self.assertRaises(ValidationError):
            version.save()
        tag = QuestionTag.objects.create(name="Daily", slug="daily")
        with self.assertRaises(ValidationError):
            version.tags.add(tag)

    def test_review_history_cannot_be_updated_or_deleted(self):
        version = self.make_version(task_type="solo", topic="daily_life", prompt_text="Prompt")
        review = QuestionReview.objects.create(
            question_version=version, reviewer=self.reviewer, decision=QuestionReview.Decision.APPROVED,
        )
        review.note = "changed"
        with self.assertRaises(ValidationError):
            review.save()
        with self.assertRaises(ValidationError):
            review.delete()


class QuestionBankWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher_group = Group.objects.create(name="teacher")
        cls.admin_group = Group.objects.create(name="admin")
        cls.teacher = User.objects.create_user(username="bank-teacher", password="demo-password-12345")
        cls.reviewer = User.objects.create_user(username="bank-reviewer", password="demo-password-67890")
        cls.other = User.objects.create_user(username="other-teacher", password="demo-password-54321")
        cls.teacher.groups.add(cls.teacher_group)
        cls.reviewer.groups.add(cls.teacher_group)
        cls.other.groups.add(cls.teacher_group)
        cls.course = Course.objects.create(code="GT1", name="Giao tiếp 1")
        cls.other_course = Course.objects.create(code="GTX", name="Ngoài phân công")
        CourseTeachingAssignment.objects.create(teacher=cls.teacher, course=cls.course)
        CourseTeachingAssignment.objects.create(teacher=cls.reviewer, course=cls.course)

    def version_post(self, **extra):
        data = {
            "course": self.course.pk, "language": "en", "task_type": "solo", "topic": "daily life",
            "target_level_min": "A1", "target_level_max": "A2", "prompt_text": "Test prompt",
            "candidate_instructions": "Answer briefly", "prep_seconds": "30", "response_seconds": "60",
            "required_points": "[]", "optional_prompts": "[]", "allowed_alternatives": "[]",
            "criterion_refs": "[]", "source_reference": "", "source_notes": "",
        }
        data.update(extra)
        return data

    def test_teacher_crud_is_scoped_and_server_rejects_other_course(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("question_create")).status_code, 200)
        response = self.client.post(reverse("question_create"), self.version_post(course=self.other_course.pk))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.exists())
        response = self.client.post(reverse("question_create"), self.version_post(
            created_by=self.reviewer.pk, status=QuestionVersion.Status.APPROVED, version="99",
        ))
        self.assertEqual(response.status_code, 302)
        version = QuestionVersion.objects.get()
        self.assertEqual(version.status, QuestionVersion.Status.DRAFT)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.created_by, self.teacher)
        self.assertEqual(version.question.created_by, self.teacher)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("question_detail", args=[version.question_id])).status_code, 404)

    def test_review_lifecycle_revision_and_retirement(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse("question_create"), self.version_post())
        version = QuestionVersion.objects.get()
        self.assertEqual(self.client.get(reverse("question_submit_review", args=[version.pk])).status_code, 403)
        response = self.client.post(reverse("question_submit_review", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, QuestionVersion.Status.IN_REVIEW)
        response = self.client.post(reverse("question_review", args=[version.pk]), {
            "decision": QuestionReview.Decision.APPROVED, "note": "",
        })
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.reviewer)
        response = self.client.post(reverse("question_review", args=[version.pk]), {
            "decision": QuestionReview.Decision.CHANGES_REQUESTED, "note": "Please clarify",
        })
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, QuestionVersion.Status.DRAFT)
        self.assertEqual(version.reviews.count(), 1)
        self.client.post(reverse("question_submit_review", args=[version.pk]))
        response = self.client.post(reverse("question_review", args=[version.pk]), {
            "decision": QuestionReview.Decision.APPROVED, "note": "",
        })
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, QuestionVersion.Status.APPROVED)
        response = self.client.post(reverse("question_new_revision", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        newer = QuestionVersion.objects.get(version=2)
        self.assertEqual(newer.status, QuestionVersion.Status.DRAFT)
        self.assertEqual(newer.prompt_text, version.prompt_text)
        version.refresh_from_db()
        self.assertEqual(version.status, QuestionVersion.Status.APPROVED)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(reverse("question_retire", args=[version.pk])).status_code, 403)
        admin = get_user_model().objects.create_user(username="content-admin", password="demo-password-99999")
        admin.groups.add(self.admin_group)
        self.client.force_login(admin)
        self.assertEqual(self.client.post(reverse("question_retire", args=[version.pk])).status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, QuestionVersion.Status.RETIRED)

    def test_unassigned_and_student_users_cannot_access_bank_and_csrf_is_required(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("question_bank")).status_code, 200)
        self.assertEqual(self.client.get(reverse("question_create")).status_code, 200)
        student = get_user_model().objects.create_user(username="bank-student", password="demo-password-24680")
        student.groups.add(Group.objects.create(name="student"))
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse("question_bank")).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.teacher)
        self.assertEqual(csrf_client.post(reverse("question_create"), self.version_post()).status_code, 403)

    def test_json_import_creates_drafts_with_exam_metadata(self):
        self.client.force_login(self.teacher)
        payload = [{
            "language": "en", "task_type": "short_qa", "topic": "Daily life",
            "target_level_min": "A1", "target_level_max": "A2", "prompt_text": "Describe your morning.",
            "prep_seconds": 10, "response_seconds": 40, "source_reference": "GT1 source p. 12",
            "exam_metadata": {"content_family": "topic-b", "sentence_type": "declarative", "phoneme_targets": ["/i:/"]},
        }]
        response = self.client.post(reverse("question_import"), {"course": self.course.pk, "payload": json.dumps(payload)})
        self.assertRedirects(response, reverse("question_bank"))
        version = QuestionVersion.objects.get()
        self.assertEqual(version.status, QuestionVersion.Status.DRAFT)
        self.assertEqual(version.exam_metadata["content_family"], "topic-b")


class RubricWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher_group = Group.objects.create(name="teacher")
        cls.admin_group = Group.objects.create(name="admin")
        cls.teacher = User.objects.create_user(username="rubric-teacher", password="rubric-password-12345")
        cls.colleague = User.objects.create_user(username="rubric-colleague", password="rubric-password-67890")
        cls.outsider = User.objects.create_user(username="rubric-outsider", password="rubric-password-54321")
        cls.teacher.groups.add(cls.teacher_group)
        cls.colleague.groups.add(cls.teacher_group)
        cls.outsider.groups.add(cls.teacher_group)
        cls.course = Course.objects.create(code="RGT1", name="Rubric Giao tiếp 1")
        cls.other_course = Course.objects.create(code="RGTX", name="Ngoài phân công")
        CourseTeachingAssignment.objects.create(teacher=cls.teacher, course=cls.course)
        CourseTeachingAssignment.objects.create(teacher=cls.colleague, course=cls.course)

    def criteria(self, descriptor="Nêu được thông tin liên quan.", max_points=None):
        return [{
            "name": "Tiêu chí kiểm thử",
            "description": "Mô tả được cung cấp bởi giảng viên.",
            "weight": "100",
            "signal": "llm",
            "max_points": max_points,
            "descriptors": [{"level": str(level), "text": descriptor if level == 0 else f"Mô tả band {level}."} for level in range(5)],
        }]

    def rubric_post(self, course=None, criteria=None, **extra):
        data = {
            "course": course or self.course.pk,
            "title": "Rubric phần nói",
            "section_name": "Task 1",
            "task_type": "solo_response",
            "target_level_min": "A1",
            "target_level_max": "A2",
            "source_reference": "Đáp án GT1, trang được xác minh",
            "source_notes": "Nội dung thử nghiệm do giảng viên cung cấp.",
            "criteria_payload": json.dumps(criteria or self.criteria()),
        }
        data.update(extra)
        return data

    def create_rubric(self, **kwargs):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("rubric_create"), self.rubric_post(**kwargs))
        self.assertEqual(response.status_code, 302)
        return Rubric.objects.filter(course=self.course).order_by("-pk").first()

    def test_rubric_crud_creates_immutable_audited_publication_and_revision(self):
        rubric = self.create_rubric(criteria=self.criteria(max_points="2.5"))
        self.assertContains(self.client.get(reverse("rubric_detail", args=[rubric.pk])), "Rubric phần nói")
        version = rubric.versions.get()
        self.assertEqual(version.status, RubricVersion.Status.DRAFT)
        criterion = version.criteria.get()
        self.assertEqual(str(criterion.max_points), "2.50")
        self.assertEqual(criterion.descriptors.count(), 5)
        self.assertEqual(version.audit_events.count(), 1)
        self.assertEqual(version.audit_events.first().action, RubricAuditEvent.Action.CREATED)

        response = self.client.post(reverse("rubric_edit", args=[version.pk]), self.rubric_post(
            criteria=self.criteria(descriptor="Phiên bản chỉnh sửa."),
        ))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.audit_events.count(), 2)
        self.assertIn("Phiên bản chỉnh sửa", version.audit_events.order_by("-id").first().after_snapshot["criteria"][0]["descriptors"][0]["text"])

        response = self.client.post(reverse("rubric_publish", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, RubricVersion.Status.PUBLISHED)
        self.assertIsNotNone(version.published_at)
        self.assertEqual(version.audit_events.count(), 3)
        locked_criterion = version.criteria.get()
        locked_criterion.name = "Không được sửa"
        with self.assertRaises(ValidationError):
            locked_criterion.save()
        descriptor = version.criteria.get().descriptors.first()
        descriptor.text = "Không được sửa"
        with self.assertRaises(ValidationError):
            descriptor.save()
        with self.assertRaises(ValidationError), transaction.atomic():
            version.criteria.all().delete()
        with self.assertRaises(ValidationError), transaction.atomic():
            version.audit_events.all().delete()
        with self.assertRaises(ValidationError):
            version.delete()

        response = self.client.post(reverse("rubric_new_revision", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        revision = rubric.versions.get(version=2)
        self.assertEqual(revision.status, RubricVersion.Status.DRAFT)
        self.assertEqual(revision.content_snapshot()["criteria"], version.content_snapshot()["criteria"])
        self.assertEqual(revision.audit_events.get().action, RubricAuditEvent.Action.REVISION_CREATED)
        response = self.client.post(reverse("rubric_edit", args=[revision.pk]), self.rubric_post(
            criteria=self.criteria(descriptor="Chỉ đổi bản nháp mới."),
        ))
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertIn("Phiên bản chỉnh sửa", version.content_snapshot()["criteria"][0]["descriptors"][0]["text"])
        self.assertEqual(revision.audit_events.count(), 2)

    def test_rubric_validation_course_scope_role_and_retirement(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("rubric_create"), self.rubric_post(
            course=self.other_course.pk,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Rubric.objects.exists())
        invalid = self.criteria()
        invalid[0]["descriptors"][0]["level"] = "C9"
        response = self.client.post(reverse("rubric_create"), self.rubric_post(criteria=invalid))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Rubric.objects.exists())
        malformed = self.criteria()
        malformed[0]["descriptors"][0]["level"] = []
        response = self.client.post(reverse("rubric_create"), self.rubric_post(criteria=malformed))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Rubric.objects.exists())

        incomplete = self.criteria()
        incomplete[0]["descriptors"] = [{"level": "0", "text": "Chỉ có band 0."}]
        rubric = self.create_rubric(criteria=incomplete)
        draft = rubric.versions.get()
        response = self.client.post(reverse("rubric_publish", args=[draft.pk]))
        self.assertEqual(response.status_code, 400)
        draft.refresh_from_db()
        self.assertEqual(draft.status, RubricVersion.Status.DRAFT)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("rubric_bank")).status_code, 200)
        self.client.force_login(get_user_model().objects.create_user(
            username="rubric-student", password="rubric-password-00000",
        ))
        self.assertEqual(self.client.get(reverse("rubric_bank")).status_code, 403)

        rubric = self.create_rubric()
        version = rubric.versions.get()
        self.client.post(reverse("rubric_publish", args=[version.pk]))
        admin = get_user_model().objects.create_user(username="rubric-admin", password="rubric-password-admin")
        admin.groups.add(self.admin_group)
        self.client.force_login(admin)
        self.assertEqual(self.client.post(reverse("rubric_retire", args=[version.pk])).status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, RubricVersion.Status.RETIRED)
        self.assertEqual(version.audit_events.order_by("-id").first().action, RubricAuditEvent.Action.RETIRED)

    def test_rubric_csrf_and_audit_events_are_append_only(self):
        rubric = self.create_rubric()
        self.assertContains(self.client.get(reverse("rubric_bank")), "Rubric phần nói")
        event = rubric.versions.get().audit_events.get()
        event.action = RubricAuditEvent.Action.UPDATED
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.teacher)
        self.assertEqual(csrf_client.post(reverse("rubric_publish", args=[event.rubric_version_id])).status_code, 403)


class BlueprintSamplingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher = User.objects.create_user(username="blueprint-teacher", password="test-password-12345")
        cls.other = User.objects.create_user(username="blueprint-other", password="test-password-67890")
        Group.objects.get_or_create(name="teacher")
        cls.teacher.groups.add(Group.objects.get(name="teacher"))
        cls.course = Course.objects.create(code="BGT1", name="Blueprint GT1")
        CourseTeachingAssignment.objects.create(teacher=cls.teacher, course=cls.course)

    def setUp(self):
        rubric = Rubric.objects.create(course=self.course, created_by=self.teacher)
        self.rubric_version = RubricVersion.objects.create(
            rubric=rubric, version=1, created_by=self.teacher, title="Rubric Task 1",
            section_name="Task 1", task_type="solo", target_level_min="A1", target_level_max="A2",
            source_reference="Nguồn đáp án do giảng viên xác nhận",
        )
        criterion = RubricCriterion.objects.create(
            rubric_version=self.rubric_version, position=1, name="Đáp ứng nhiệm vụ", weight="100",
        )
        for level in range(5):
            CriterionLevelDescriptor.objects.create(criterion=criterion, level=str(level), text=f"Descriptor {level}")
        self.rubric_version.status = RubricVersion.Status.PUBLISHED
        from django.utils import timezone
        self.rubric_version.published_at = timezone.now()
        self.rubric_version.save()
        self.blueprint = ExamBlueprint.objects.create(course=self.course, created_by=self.teacher)
        self.version = BlueprintVersion.objects.create(
            blueprint=self.blueprint, version=1, created_by=self.teacher, title="Blueprint thử",
            source_reference="Cấu hình đề đã được giảng viên đối chiếu",
        )
        BlueprintSlot.objects.create(
            blueprint_version=self.version, position=1, section_name="Task 1", task_type="solo",
            question_count=1, target_level_min="A1", target_level_max="A2", language="en",
            prep_seconds=30, response_seconds=60, rubric_version=self.rubric_version,
        )

    def add_question(self, prompt, *, topic="Daily life", status=QuestionVersion.Status.APPROVED):
        question = Question.objects.create(course=self.course, created_by=self.teacher)
        version = QuestionVersion.objects.create(
            question=question, version=1, created_by=self.teacher, language="en", task_type="solo",
            topic=topic, target_level_min="A1", target_level_max="A2", prompt_text=prompt,
            prep_seconds=30, response_seconds=60, source_reference="Đề giấy, trang đã kiểm tra",
        )
        if status != QuestionVersion.Status.DRAFT:
            version.status = QuestionVersion.Status.IN_REVIEW
            version.save()
            version.status = status
            version.save()
        return version

    def test_gt1_schema_rejects_missing_required_sections(self):
        self.version.assessment_type = "gt1"
        self.version.save(update_fields=("assessment_type",))
        with self.assertRaises(ValidationError):
            self.version.validate_for_publication()

    def test_sample_is_repeatable_and_snapshots_question_rubric_and_pool(self):
        question = self.add_question("Describe your day")
        first = sample_blueprint(blueprint_version=self.version, topic="Daily life", created_by=self.teacher, seed=42)
        second = sample_blueprint(blueprint_version=self.version, topic="Daily life", created_by=self.teacher, seed=42)
        self.assertEqual(first.selected_snapshot, second.selected_snapshot)
        self.assertEqual(first.selected_snapshot[0]["questions"][0]["version_id"], question.pk)
        self.assertEqual(first.selected_snapshot[0]["rubric_version_id"], self.rubric_version.pk)
        self.assertEqual(first.candidate_pool_snapshot[0]["candidate_version_ids"], [question.pk])

    def test_sample_refuses_shortage_without_relaxing_topic_or_approval(self):
        self.add_question("Wrong topic", topic="Travel")
        self.add_question("Unapproved", status=QuestionVersion.Status.DRAFT)
        with self.assertRaises(InsufficientQuestionPool) as caught:
            sample_blueprint(blueprint_version=self.version, topic="Daily life", created_by=self.teacher, seed=1)
        self.assertEqual(caught.exception.shortages[0]["eligible_pool"], 0)
        self.assertFalse(self.version.samples.exists())

    def test_teacher_cannot_access_unassigned_blueprint_and_sample_requires_post(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("blueprint_detail", args=[self.blueprint.pk])).status_code, 403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("blueprint_bank")).status_code, 200)
        self.assertEqual(self.client.get(reverse("blueprint_detail", args=[self.blueprint.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("blueprint_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("blueprint_sample", args=[self.version.pk])).status_code, 403)


class PracticeWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.student = User.objects.create_user(username="practice-student", password="practice-password-12345")
        cls.other = User.objects.create_user(username="practice-other", password="practice-password-67890")
        cls.teacher = User.objects.create_user(username="practice-teacher", password="practice-password-teacher")
        cls.student.groups.add(Group.objects.create(name="student"))
        cls.teacher.groups.add(Group.objects.create(name="teacher"))
        cls.course = Course.objects.create(code="GT1", name="Giao tiếp 1")
        Enrollment.objects.create(student=cls.student, course=cls.course)
        CourseTeachingAssignment.objects.create(teacher=cls.teacher, course=cls.course)

    def complete_preflight(self, attempt):
        response = self.client.get(reverse("practice_detail", args=[attempt.pk]))
        self.assertEqual(response.status_code, 302)
        setup = self.client.session[f"speaking_preflight:{self.student.pk}"]
        ready = self.client.post(reverse("practice_preflight_complete"), {
            "nonce": setup["nonce"], "mic_verified": "1", "playback_confirmed": "1",
            "speed_bps": 40000, "latency_ms": 100,
        })
        self.assertEqual(ready.status_code, 200)
        return self.client.post(reverse("practice_start"))

    def test_student_can_generate_and_open_ai_practice(self):
        self.client.force_login(self.student)
        dashboard = self.client.get(reverse("dashboard_student"))
        self.assertContains(dashboard, "Tạo bài luyện")
        self.assertContains(dashboard, "Giao tiếp 1")
        config = self.client.get(reverse("practice_create"))
        self.assertEqual(config.context["form"]["course"].value(), self.course.pk)
        with patch("core.views.generate_practice_questions", return_value={
            "model": "local-test-model", "topic": "Daily life",
            "questions": [{"prompt": "Describe your morning.", "candidate_instructions": "Speak clearly."}],
        }):
            response = self.client.post(reverse("practice_create"), {
                "course": self.course.pk, "level": "A1", "topic": "", "question_count": 1,
                "response_seconds": 45,
            })
        self.assertRedirects(response, reverse("practice_preflight"))
        self.assertFalse(PracticeAttempt.objects.filter(student=self.student).exists())
        preflight = self.client.get(reverse("practice_preflight"))
        self.assertContains(preflight, "Bắt đầu kiểm tra micro")
        self.assertContains(preflight, "Kiểm tra tốc độ mạng")
        setup = self.client.session[f"speaking_preflight:{self.student.pk}"]
        blocked = self.client.post(reverse("practice_start"))
        self.assertRedirects(blocked, reverse("practice_preflight"))
        self.assertFalse(PracticeAttempt.objects.filter(student=self.student).exists())
        ready = self.client.post(reverse("practice_preflight_complete"), {
            "nonce": setup["nonce"], "mic_verified": "1", "playback_confirmed": "1",
            "speed_bps": 40000, "latency_ms": 100,
        })
        self.assertEqual(ready.status_code, 200)
        with patch("core.views.generate_practice_questions", return_value={
            "model": "local-test-model", "topic": "Daily life",
            "questions": [{"prompt": "Describe your morning.", "candidate_instructions": "Speak clearly."}],
        }):
            response = self.client.post(reverse("practice_start"))
        attempt = PracticeAttempt.objects.get(student=self.student)
        self.assertRedirects(response, reverse("practice_detail", args=[attempt.pk]))
        self.assertContains(self.client.get(response.url), "Describe your morning.")
        self.assertEqual(attempt.response_seconds, 45)

    def test_preflight_completion_rejects_low_speed_and_network_probe_requires_student(self):
        self.client.force_login(self.student)
        self.client.post(reverse("practice_create"), {
            "course": self.course.pk, "level": "A1", "topic": "", "question_count": 1,
            "response_seconds": 45,
        })
        setup = self.client.session[f"speaking_preflight:{self.student.pk}"]
        rejected = self.client.post(reverse("practice_preflight_complete"), {
            "nonce": setup["nonce"], "mic_verified": "1", "playback_confirmed": "1",
            "speed_bps": 1000, "latency_ms": 100,
        })
        self.assertEqual(rejected.status_code, 400)
        ping = self.client.generic("POST", reverse("network_probe"), b"", content_type="application/octet-stream")
        self.assertEqual(ping.status_code, 204)
        transfer = self.client.post(reverse("network_probe"), data=b"x" * 262144,
                                    content_type="application/octet-stream")
        self.assertEqual(transfer.status_code, 200)
        self.assertEqual(len(transfer.content), 262144)

    def test_audio_answer_is_private_and_submission_requires_all_answers(self):
        attempt = PracticeAttempt.objects.create(
            student=self.student, course=self.course, cefr_level="A1", topic="Daily life",
            question_count=1, response_seconds=45, ai_model="local-test-model",
            questions=[{"prompt": "Describe your morning.", "candidate_instructions": ""}],
        )
        self.client.force_login(self.student)
        self.assertRedirects(self.complete_preflight(attempt), reverse("practice_detail", args=[attempt.pk]))
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse("practice_answer_upload", args=[attempt.pk]), {
                "question_index": 1, "duration_seconds": 4,
                "audio": SimpleUploadedFile("answer.webm", b"\x1a\x45\xdf\xa3" + b"\0" * 32, content_type="audio/webm"),
            })
            self.assertRedirects(response, reverse("practice_detail", args=[attempt.pk]))
            answer = PracticeAnswer.objects.get(attempt=attempt)
            self.assertEqual(self.client.get(reverse("practice_answer_audio", args=[answer.pk])).status_code, 200)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(reverse("practice_answer_audio", args=[answer.pk])).status_code, 403)
            self.client.force_login(self.teacher)
            self.assertEqual(self.client.get(reverse("dashboard_teacher")).status_code, 200)
            self.assertEqual(self.client.get(reverse("practice_review", args=[attempt.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("practice_answer_audio", args=[answer.pk])).status_code, 200)
            self.client.force_login(self.student)
            self.complete_preflight(attempt)
            self.assertEqual(self.client.post(reverse("practice_submit", args=[attempt.pk])).status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, PracticeAttempt.Status.SUBMITTED)

    def test_existing_attempt_requires_preflight_before_view_or_upload(self):
        attempt = PracticeAttempt.objects.create(
            student=self.student, course=self.course, cefr_level="A1", topic="Daily life",
            question_count=1, response_seconds=45, ai_model="local-test-model",
            questions=[{"prompt": "Say hello.", "candidate_instructions": ""}],
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("practice_detail", args=[attempt.pk]))
        self.assertRedirects(response, reverse("practice_preflight"))
        self.assertEqual(
            self.client.session[f"speaking_preflight:{self.student.pk}"]["attempt_id"], attempt.pk,
        )
        response = self.client.post(reverse("practice_answer_upload", args=[attempt.pk]), {
            "question_index": 1, "duration_seconds": 2,
            "audio": SimpleUploadedFile("answer.webm", b"\x1a\x45\xdf\xa3" + b"\0" * 32, content_type="audio/webm"),
        })
        self.assertRedirects(response, reverse("practice_detail", args=[attempt.pk]), fetch_redirect_response=False)
        self.assertFalse(PracticeAnswer.objects.filter(attempt=attempt).exists())
        self.assertRedirects(
            self.client.post(reverse("practice_submit", args=[attempt.pk])),
            reverse("practice_detail", args=[attempt.pk]), fetch_redirect_response=False,
        )
        setup = self.client.session[f"speaking_preflight:{self.student.pk}"]
        self.client.post(reverse("practice_preflight_complete"), {
            "nonce": setup["nonce"], "mic_verified": "1", "playback_confirmed": "1",
            "speed_bps": 40000, "latency_ms": 100,
        })
        self.assertRedirects(self.client.post(reverse("practice_start")), reverse("practice_detail", args=[attempt.pk]))
        self.assertContains(self.client.get(reverse("practice_detail", args=[attempt.pk])), "Say hello.")

    def test_invalid_audio_mime_is_rejected(self):
        attempt = PracticeAttempt.objects.create(
            student=self.student, course=self.course, cefr_level="A1", topic="Daily life",
            question_count=1, response_seconds=45, ai_model="local-test-model",
            questions=[{"prompt": "Say hello.", "candidate_instructions": ""}],
        )
        self.client.force_login(self.student)
        self.assertRedirects(self.complete_preflight(attempt), reverse("practice_detail", args=[attempt.pk]))
        response = self.client.post(reverse("practice_answer_upload", args=[attempt.pk]), {
            "question_index": 1, "duration_seconds": 3,
            "audio": SimpleUploadedFile("bad.txt", b"not audio", content_type="text/plain"),
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PracticeAnswer.objects.filter(attempt=attempt).exists())


class OfficialExamWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.student = User.objects.create_user(username="official-student", password="official-password-12345")
        cls.teacher = User.objects.create_user(username="official-teacher", password="official-password-12345")
        cls.student.groups.add(Group.objects.get_or_create(name="student")[0])
        cls.teacher.groups.add(Group.objects.get_or_create(name="teacher")[0])
        cls.course = Course.objects.create(code="OFGT1", name="Official GT1")
        Enrollment.objects.create(student=cls.student, course=cls.course)
        CourseTeachingAssignment.objects.create(teacher=cls.teacher, course=cls.course)

    def setUp(self):
        from django.utils import timezone
        rubric = Rubric.objects.create(course=self.course, created_by=self.teacher)
        self.rubric_version = RubricVersion.objects.create(
            rubric=rubric, version=1, created_by=self.teacher, title="Official rubric",
            section_name="A", task_type="solo", target_level_min="A1", target_level_max="A2",
            source_reference="Official source",
        )
        criterion = RubricCriterion.objects.create(
            rubric_version=self.rubric_version, position=1, name="task_achievement", weight="100", signal="manual",
        )
        for level in range(5):
            CriterionLevelDescriptor.objects.create(criterion=criterion, level=str(level), text=f"Band {level}")
        self.rubric_version.status = RubricVersion.Status.PUBLISHED
        self.rubric_version.published_at = timezone.now()
        self.rubric_version.save()
        blueprint = ExamBlueprint.objects.create(course=self.course, created_by=self.teacher)
        self.blueprint_version = BlueprintVersion.objects.create(
            blueprint=blueprint, version=1, created_by=self.teacher, title="Official blueprint",
            source_reference="Official blueprint source", pass_threshold="1.00",
        )
        BlueprintSlot.objects.create(
            blueprint_version=self.blueprint_version, position=1, section_name="A", task_type="solo",
            question_count=1, target_level_min="A1", target_level_max="A2", language="en",
            prep_seconds=1, response_seconds=10, selection_rules={"topics": ["Daily life"]}, max_points="2.00",
            rubric_version=self.rubric_version,
        )
        self.blueprint_version.status = BlueprintVersion.Status.PUBLISHED
        self.blueprint_version.published_at = timezone.now()
        self.blueprint_version.save()
        question = Question.objects.create(course=self.course, created_by=self.teacher)
        self.question_version = QuestionVersion.objects.create(
            question=question, version=1, created_by=self.teacher, language="en", task_type="solo",
            topic="Daily life", target_level_min="A1", target_level_max="A2", prompt_text="Describe your day.",
            prep_seconds=1, response_seconds=10, source_reference="Approved official source",
            exam_metadata={"content_family": "daily-1"},
        )
        self.question_version.status = QuestionVersion.Status.IN_REVIEW
        self.question_version.save()
        self.question_version.status = QuestionVersion.Status.APPROVED
        self.question_version.save()

    def complete_exam_preflight(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("exam_start", args=[self.blueprint_version.pk]), {"topic": "Daily life"})
        self.assertRedirects(response, reverse("exam_preflight"))
        setup = self.client.session[f"official_preflight:{self.student.pk}"]
        response = self.client.post(reverse("exam_preflight_complete"), {
            "nonce": setup["nonce"], "mic_verified": "1", "playback_confirmed": "1",
            "speed_bps": 40_000, "latency_ms": 100,
        })
        self.assertEqual(response.status_code, 200)
        return self.client.post(reverse("exam_preflight_begin"))

    def test_official_start_requires_preflight_and_snapshots_with_timebox(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("exam_start", args=[self.blueprint_version.pk]), {"topic": "Daily life"})
        self.assertRedirects(response, reverse("exam_preflight"))
        self.assertFalse(ExamAttempt.objects.exists())
        response = self.complete_exam_preflight()
        attempt = ExamAttempt.objects.get()
        self.assertRedirects(response, reverse("exam_detail", args=[attempt.pk]))
        self.assertEqual(attempt.threshold, 1)
        self.assertIsNotNone(attempt.started_at)
        self.assertIsNotNone(attempt.expires_at)
        self.assertEqual(attempt.questions_snapshot[0]["question"]["version_id"], self.question_version.pk)

    def test_submit_requires_audio_and_scoring_sets_pass(self):
        self.complete_exam_preflight()
        attempt = ExamAttempt.objects.get()
        wav = b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + (0).to_bytes(4, "little")
        blocked = self.client.post(reverse("exam_submit", args=[attempt.pk]))
        self.assertRedirects(blocked, reverse("exam_detail", args=[attempt.pk]))
        response = self.client.post(reverse("exam_answer_upload", args=[attempt.pk]), {
            "question_index": 1, "duration_seconds": 1,
            "audio": SimpleUploadedFile("answer.wav", wav, content_type="audio/wav"),
        })
        self.assertRedirects(response, reverse("exam_detail", args=[attempt.pk]))
        self.assertEqual(ExamAnswer.objects.filter(attempt=attempt).count(), 1)
        self.assertEqual(self.client.post(reverse("exam_submit", args=[attempt.pk])).status_code, 302)
        attempt.refresh_from_db()
        payload = [{"question_index": 1, "criteria": [{"name": "task_achievement", "band": 4, "evidence": "Đủ ý"}]}]
        result = score_official_attempt(attempt=attempt, answers_payload=payload, actor=self.teacher, reason="Đã nghe lại audio.")
        self.assertEqual(result["status"], "scored")
        attempt.refresh_from_db()
        self.assertEqual(attempt.final_score, 2)
        self.assertTrue(attempt.passed)
        with self.assertRaises(ValidationError):
            score_official_attempt(attempt=attempt, answers_payload=payload, actor=self.teacher, reason="Chấm lại")

    def test_review_queue_claims_submitted_attempt(self):
        from django.utils import timezone
        attempt = ExamAttempt.objects.create(
            student=self.student, course=self.course, blueprint_version=self.blueprint_version, seed=1,
            blueprint_snapshot=self.blueprint_version.content_snapshot(), questions_snapshot=[],
            status=ExamAttempt.Status.SUBMITTED, submitted_at=timezone.now(),
        )
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse("exam_review_queue")), self.student.username)
        response = self.client.post(reverse("exam_review_claim", args=[attempt.pk]))
        self.assertRedirects(response, reverse("exam_review_queue"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.reviewed_by_id, self.teacher.pk)
