from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, PROTECT, Q
from django.db.models.signals import m2m_changed, pre_delete
from django.dispatch import receiver


CEFR_LEVELS = (("A1", "A1"), ("A2", "A2"), ("B1", "B1"), ("B2", "B2"), ("C1", "C1"))
CEFR_ORDER = {level: index for index, (level, _) in enumerate(CEFR_LEVELS)}


class Course(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} — {self.name}"


class CourseTeachingAssignment(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="teaching_assignments"
    )
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="teaching_assignments")
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("course__code", "teacher__username")
        constraints = [
            models.UniqueConstraint(fields=("teacher", "course"), name="unique_teacher_course_assignment"),
        ]

    def __str__(self):
        return f"{self.teacher} · {self.course.code}"


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="course_enrollments"
    )
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("course__code", "student__username")
        constraints = [
            models.UniqueConstraint(fields=("student", "course"), name="unique_student_course_enrollment"),
        ]
        indexes = [models.Index(fields=("course", "student"), name="enrollment_course_student_idx")]

    def __str__(self):
        return f"{self.student} · {self.course.code}"


class Question(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="questions")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_questions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("course__code", "id")

    def __str__(self):
        return f"{self.course.code} · Question {self.pk}"


class QuestionTag(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class QuestionVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        APPROVED = "approved", "Approved"
        RETIRED = "retired", "Retired"

    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_question_versions"
    )
    language = models.CharField(max_length=16, default="en")
    task_type = models.CharField(max_length=64)
    topic = models.CharField(max_length=160)
    target_level_min = models.CharField(max_length=2, choices=CEFR_LEVELS, blank=True)
    target_level_max = models.CharField(max_length=2, choices=CEFR_LEVELS, blank=True)
    prompt_text = models.TextField()
    candidate_instructions = models.TextField(blank=True)
    prep_seconds = models.PositiveIntegerField(null=True, blank=True)
    response_seconds = models.PositiveIntegerField(null=True, blank=True)
    required_points = models.JSONField(default=list, blank=True)
    optional_prompts = models.JSONField(default=list, blank=True)
    allowed_alternatives = models.JSONField(default=list, blank=True)
    criterion_refs = models.JSONField(default=list, blank=True)
    source_reference = models.CharField(max_length=255, blank=True)
    source_notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    tags = models.ManyToManyField(QuestionTag, blank=True, related_name="question_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("question_id", "version")
        constraints = [
            models.UniqueConstraint(fields=("question", "version"), name="unique_question_version_number"),
            models.CheckConstraint(condition=Q(version__gte=1), name="question_version_positive"),
            models.CheckConstraint(
                condition=(
                    Q(target_level_min="")
                    | Q(target_level_max="")
                    | Q(target_level_min__lte=F("target_level_max"))
                ),
                name="question_level_range_ordered",
            ),
        ]
        indexes = [models.Index(fields=("status", "topic"), name="qversion_status_topic_idx")]

    def clean(self):
        super().clean()
        if (
            self.target_level_min
            and self.target_level_max
            and self.target_level_min in CEFR_ORDER
            and self.target_level_max in CEFR_ORDER
            and CEFR_ORDER[self.target_level_min] > CEFR_ORDER[self.target_level_max]
        ):
            raise ValidationError({"target_level_max": "Mức tối đa phải bằng hoặc cao hơn mức tối thiểu."})

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.status != self.Status.DRAFT:
                raise ValidationError("Phiên bản câu hỏi mới phải bắt đầu ở trạng thái nháp.")
        else:
            previous = type(self).objects.get(pk=self.pk)
            content_fields = (
                "question_id", "version", "created_by_id", "language", "task_type", "topic",
                "target_level_min", "target_level_max", "prompt_text", "candidate_instructions",
                "prep_seconds", "response_seconds", "required_points", "optional_prompts",
                "allowed_alternatives", "criterion_refs", "source_reference", "source_notes",
            )
            if previous.status != self.Status.DRAFT and any(
                getattr(previous, field) != getattr(self, field) for field in content_fields
            ):
                raise ValidationError("Chỉ phiên bản nháp mới được chỉnh sửa nội dung.")
            transitions = {
                self.Status.DRAFT: {self.Status.DRAFT, self.Status.IN_REVIEW},
                self.Status.IN_REVIEW: {self.Status.IN_REVIEW, self.Status.DRAFT, self.Status.APPROVED},
                self.Status.APPROVED: {self.Status.APPROVED, self.Status.RETIRED},
                self.Status.RETIRED: {self.Status.RETIRED},
            }
            if self.status not in transitions[previous.status]:
                raise ValidationError("Chuyển trạng thái phiên bản không hợp lệ.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.question} v{self.version}"


class QuestionReview(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"

    question_version = models.ForeignKey(
        QuestionVersion, on_delete=models.PROTECT, related_name="reviews"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="question_reviews"
    )
    decision = models.CharField(max_length=24, choices=Decision.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def clean(self):
        super().clean()
        if self.question_version_id and self.reviewer_id:
            if self.question_version.created_by_id == self.reviewer_id:
                raise ValidationError({"reviewer": "Người tạo phiên bản không thể tự duyệt phiên bản đó."})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Lịch sử duyệt là bất biến.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa lịch sử duyệt.")

    def __str__(self):
        return f"{self.question_version} · {self.get_decision_display()}"


class Rubric(models.Model):
    course = models.ForeignKey(Course, on_delete=PROTECT, related_name="rubrics")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="created_rubrics"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("course__code", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            if (previous.course_id, previous.created_by_id) != (self.course_id, self.created_by_id):
                raise ValidationError("Không thể đổi học phần hoặc tác giả của rubric.")
        return super().save(*args, **kwargs)

    def __str__(self):
        latest = self.versions.order_by("-version").first()
        return f"{self.course.code} · {latest.title if latest else 'Rubric'}"


class RubricVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Nháp"
        PUBLISHED = "published", "Đã xuất bản"
        RETIRED = "retired", "Ngừng sử dụng"

    rubric = models.ForeignKey(Rubric, on_delete=PROTECT, related_name="versions")
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="created_rubric_versions"
    )
    title = models.CharField(max_length=160)
    section_name = models.CharField(max_length=120)
    task_type = models.CharField(max_length=80)
    target_level_min = models.CharField(max_length=2, choices=CEFR_LEVELS, blank=True)
    target_level_max = models.CharField(max_length=2, choices=CEFR_LEVELS, blank=True)
    source_reference = models.CharField(max_length=255)
    source_notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("rubric_id", "version")
        constraints = [
            models.UniqueConstraint(fields=("rubric", "version"), name="unique_rubric_version_number"),
            models.CheckConstraint(condition=Q(version__gte=1), name="rubric_version_positive"),
            models.CheckConstraint(
                condition=(Q(target_level_min="") | Q(target_level_max="") |
                           Q(target_level_min__lte=F("target_level_max"))),
                name="rubric_level_range_ordered",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.target_level_min and self.target_level_max
            and self.target_level_min in CEFR_ORDER and self.target_level_max in CEFR_ORDER
            and CEFR_ORDER[self.target_level_min] > CEFR_ORDER[self.target_level_max]
        ):
            raise ValidationError({"target_level_max": "Mức tối đa phải bằng hoặc cao hơn mức tối thiểu."})

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.status != self.Status.DRAFT or self.published_at is not None:
                raise ValidationError("Rubric version mới phải bắt đầu ở trạng thái nháp.")
        else:
            previous = type(self).objects.get(pk=self.pk)
            content_fields = (
                "rubric_id", "version", "created_by_id", "title", "section_name", "task_type",
                "target_level_min", "target_level_max", "source_reference", "source_notes",
            )
            if previous.status != self.Status.DRAFT and any(
                getattr(previous, field) != getattr(self, field) for field in content_fields
            ):
                raise ValidationError("Chỉ rubric nháp mới được chỉnh sửa nội dung.")
            if previous.status != self.Status.DRAFT and previous.published_at != self.published_at:
                raise ValidationError("Không thể thay đổi thời điểm xuất bản rubric.")
            transitions = {
                self.Status.DRAFT: {self.Status.DRAFT, self.Status.PUBLISHED},
                self.Status.PUBLISHED: {self.Status.PUBLISHED, self.Status.RETIRED},
                self.Status.RETIRED: {self.Status.RETIRED},
            }
            if self.status not in transitions[previous.status]:
                raise ValidationError("Chuyển trạng thái rubric không hợp lệ.")
            if self.status == self.Status.PUBLISHED and self.published_at is None:
                raise ValidationError("Cần ghi nhận thời điểm xuất bản rubric.")
            if self.status == self.Status.PUBLISHED and previous.status == self.Status.DRAFT:
                self.validate_for_publication()
        return super().save(*args, **kwargs)

    def content_snapshot(self):
        return {
            "title": self.title,
            "section_name": self.section_name,
            "task_type": self.task_type,
            "target_level_min": self.target_level_min,
            "target_level_max": self.target_level_max,
            "source_reference": self.source_reference,
            "source_notes": self.source_notes,
            "criteria": [
                {
                    "name": criterion.name,
                    "description": criterion.description,
                    "max_points": str(criterion.max_points) if criterion.max_points is not None else None,
                    "descriptors": [
                        {"level": descriptor.level, "text": descriptor.text}
                        for descriptor in criterion.descriptors.order_by("level")
                    ],
                }
                for criterion in self.criteria.order_by("position")
            ],
        }

    def validate_for_publication(self):
        criteria = list(self.criteria.prefetch_related("descriptors"))
        if not self.source_reference.strip() or not criteria:
            raise ValidationError("Rubric cần có nguồn và ít nhất một tiêu chí trước khi xuất bản.")
        expected_levels = None
        if self.target_level_min and self.target_level_max:
            first = CEFR_ORDER[self.target_level_min]
            last = CEFR_ORDER[self.target_level_max]
            expected_levels = {
                level for level, _ in CEFR_LEVELS
                if first <= CEFR_ORDER[level] <= last
            }
        for criterion in criteria:
            levels = {
                descriptor.level for descriptor in criterion.descriptors.all()
                if descriptor.text.strip()
            }
            if not levels:
                raise ValidationError(f"Tiêu chí '{criterion.name}' cần có descriptor theo cấp độ.")
            if expected_levels and not expected_levels.issubset(levels):
                raise ValidationError(
                    f"Tiêu chí '{criterion.name}' cần descriptor cho mọi cấp độ trong dải rubric."
                )

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa phiên bản rubric; hãy tạo bản mới hoặc ngừng sử dụng.")

    def __str__(self):
        return f"{self.rubric} v{self.version}"


class RubricCriterion(models.Model):
    rubric_version = models.ForeignKey(RubricVersion, on_delete=models.CASCADE, related_name="criteria")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    max_points = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("rubric_version", "position"), name="unique_rubric_criterion_position"),
            models.CheckConstraint(condition=Q(position__gte=1), name="rubric_criterion_position_positive"),
            models.CheckConstraint(
                condition=Q(max_points__isnull=True) | Q(max_points__gt=0),
                name="rubric_criterion_points_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.rubric_version_id and RubricVersion.objects.filter(pk=self.rubric_version_id).exclude(
            status=RubricVersion.Status.DRAFT
        ).exists():
            raise ValidationError("Không thể sửa tiêu chí của rubric đã xuất bản.")
        if self.pk:
            previous = type(self).objects.select_related("rubric_version").get(pk=self.pk)
            if previous.rubric_version.status != RubricVersion.Status.DRAFT:
                raise ValidationError("Không thể sửa tiêu chí của rubric đã xuất bản.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.rubric_version.status != RubricVersion.Status.DRAFT:
            raise ValidationError("Không thể xóa tiêu chí của rubric đã xuất bản.")
        return super().delete(*args, **kwargs)


class CriterionLevelDescriptor(models.Model):
    criterion = models.ForeignKey(RubricCriterion, on_delete=models.CASCADE, related_name="descriptors")
    level = models.CharField(max_length=2, choices=CEFR_LEVELS)
    text = models.TextField()

    class Meta:
        ordering = ("criterion__position", "level")
        constraints = [
            models.UniqueConstraint(fields=("criterion", "level"), name="unique_criterion_level_descriptor"),
        ]

    def save(self, *args, **kwargs):
        if self.criterion_id and self.criterion.rubric_version.status != RubricVersion.Status.DRAFT:
            raise ValidationError("Không thể sửa descriptor của rubric đã xuất bản.")
        if self.pk:
            previous = type(self).objects.select_related("criterion__rubric_version").get(pk=self.pk)
            if previous.criterion.rubric_version.status != RubricVersion.Status.DRAFT:
                raise ValidationError("Không thể sửa descriptor của rubric đã xuất bản.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.criterion.rubric_version.status != RubricVersion.Status.DRAFT:
            raise ValidationError("Không thể xóa descriptor của rubric đã xuất bản.")
        return super().delete(*args, **kwargs)


class RubricAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Tạo nháp"
        UPDATED = "updated", "Cập nhật nháp"
        REVISION_CREATED = "revision_created", "Tạo phiên bản mới"
        PUBLISHED = "published", "Xuất bản"
        RETIRED = "retired", "Ngừng sử dụng"

    rubric_version = models.ForeignKey(RubricVersion, on_delete=PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="rubric_audit_events")
    action = models.CharField(max_length=24, choices=Action.choices)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Lịch sử rubric là bất biến.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa lịch sử rubric.")


@receiver(pre_delete, sender=RubricCriterion)
def prevent_locked_criterion_deletion(sender, instance, **kwargs):
    if instance.rubric_version.status != RubricVersion.Status.DRAFT:
        raise ValidationError("Không thể xóa tiêu chí của rubric đã xuất bản.")


@receiver(pre_delete, sender=CriterionLevelDescriptor)
def prevent_locked_descriptor_deletion(sender, instance, **kwargs):
    if instance.criterion.rubric_version.status != RubricVersion.Status.DRAFT:
        raise ValidationError("Không thể xóa descriptor của rubric đã xuất bản.")


@receiver(pre_delete, sender=RubricAuditEvent)
def prevent_rubric_audit_deletion(sender, instance, **kwargs):
    raise ValidationError("Không thể xóa lịch sử rubric.")


class ExamBlueprint(models.Model):
    course = models.ForeignKey(Course, on_delete=PROTECT, related_name="blueprints")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="created_exam_blueprints"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("course__code", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            if (previous.course_id, previous.created_by_id) != (self.course_id, self.created_by_id):
                raise ValidationError("Không thể đổi học phần hoặc tác giả của blueprint.")
        return super().save(*args, **kwargs)

    def __str__(self):
        latest = self.versions.order_by("-version").first()
        return f"{self.course.code} · {latest.title if latest else 'Blueprint'}"


class BlueprintVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Nháp"
        PUBLISHED = "published", "Đã xuất bản"
        RETIRED = "retired", "Ngừng sử dụng"

    blueprint = models.ForeignKey(ExamBlueprint, on_delete=PROTECT, related_name="versions")
    version = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="created_blueprint_versions"
    )
    title = models.CharField(max_length=160)
    source_reference = models.CharField(max_length=255)
    source_notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("blueprint_id", "version")
        constraints = [
            models.UniqueConstraint(fields=("blueprint", "version"), name="unique_blueprint_version_number"),
            models.CheckConstraint(condition=Q(version__gte=1), name="blueprint_version_positive"),
        ]

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.status != self.Status.DRAFT or self.published_at is not None:
                raise ValidationError("Blueprint version mới phải bắt đầu ở trạng thái nháp.")
        else:
            previous = type(self).objects.get(pk=self.pk)
            locked_fields = (
                "blueprint_id", "version", "created_by_id", "title", "source_reference", "source_notes",
            )
            if previous.status != self.Status.DRAFT and any(
                getattr(previous, field) != getattr(self, field) for field in locked_fields
            ):
                raise ValidationError("Chỉ blueprint nháp mới được chỉnh sửa.")
            if previous.status != self.Status.DRAFT and previous.published_at != self.published_at:
                raise ValidationError("Không thể thay đổi thời điểm xuất bản blueprint.")
            transitions = {
                self.Status.DRAFT: {self.Status.DRAFT, self.Status.PUBLISHED},
                self.Status.PUBLISHED: {self.Status.PUBLISHED, self.Status.RETIRED},
                self.Status.RETIRED: {self.Status.RETIRED},
            }
            if self.status not in transitions[previous.status]:
                raise ValidationError("Chuyển trạng thái blueprint không hợp lệ.")
            if self.status == self.Status.PUBLISHED and self.published_at is None:
                raise ValidationError("Cần ghi nhận thời điểm xuất bản blueprint.")
            if self.status == self.Status.PUBLISHED and previous.status == self.Status.DRAFT:
                self.validate_for_publication()
        return super().save(*args, **kwargs)

    def validate_for_publication(self):
        slots = list(self.slots.select_related("rubric_version"))
        if not self.source_reference.strip() or not slots:
            raise ValidationError("Blueprint cần nguồn và ít nhất một slot trước khi xuất bản.")
        for slot in slots:
            rubric = slot.rubric_version
            if rubric.status != RubricVersion.Status.PUBLISHED:
                raise ValidationError(f"Rubric của phần '{slot.section_name}' không còn được xuất bản.")
            if (rubric.rubric.course_id != self.blueprint.course_id
                    or rubric.section_name != slot.section_name or rubric.task_type != slot.task_type):
                raise ValidationError(f"Rubric của phần '{slot.section_name}' không khớp học phần/dạng bài.")
            first, last = CEFR_ORDER[slot.target_level_min], CEFR_ORDER[slot.target_level_max]
            expected = {
                level for level, _ in CEFR_LEVELS
                if first <= CEFR_ORDER[level] <= last
            }
            criteria = list(rubric.criteria.prefetch_related("descriptors"))
            if not criteria:
                raise ValidationError(f"Rubric của phần '{slot.section_name}' chưa có tiêu chí.")
            for criterion in criteria:
                available = {item.level for item in criterion.descriptors.all() if item.text.strip()}
                if not expected.issubset(available):
                    raise ValidationError(
                        f"Rubric của phần '{slot.section_name}' thiếu descriptor cho dải cấp độ blueprint."
                    )

    def content_snapshot(self):
        return {
            "title": self.title,
            "source_reference": self.source_reference,
            "source_notes": self.source_notes,
            "slots": [
                {
                    "position": slot.position,
                    "section_name": slot.section_name,
                    "task_type": slot.task_type,
                    "question_count": slot.question_count,
                    "target_level_min": slot.target_level_min,
                    "target_level_max": slot.target_level_max,
                    "language": slot.language,
                    "prep_seconds": slot.prep_seconds,
                    "response_seconds": slot.response_seconds,
                    "rubric_version_id": slot.rubric_version_id,
                    "rubric_version": slot.rubric_version.version,
                    "rubric": slot.rubric_version.content_snapshot(),
                }
                for slot in self.slots.select_related("rubric_version").order_by("position")
            ],
        }

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa phiên bản blueprint; hãy tạo bản mới hoặc ngừng sử dụng.")

    def __str__(self):
        return f"{self.blueprint} v{self.version}"


class BlueprintAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Tạo nháp"
        UPDATED = "updated", "Cập nhật nháp"
        REVISION_CREATED = "revision_created", "Tạo phiên bản mới"
        PUBLISHED = "published", "Xuất bản"
        RETIRED = "retired", "Ngừng sử dụng"

    blueprint_version = models.ForeignKey(BlueprintVersion, on_delete=PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="blueprint_audit_events")
    action = models.CharField(max_length=24, choices=Action.choices)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Lịch sử blueprint là bất biến.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa lịch sử blueprint.")


class BlueprintSlot(models.Model):
    blueprint_version = models.ForeignKey(BlueprintVersion, on_delete=models.CASCADE, related_name="slots")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    section_name = models.CharField(max_length=120)
    task_type = models.CharField(max_length=64)
    question_count = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    target_level_min = models.CharField(max_length=2, choices=CEFR_LEVELS)
    target_level_max = models.CharField(max_length=2, choices=CEFR_LEVELS)
    language = models.CharField(max_length=16, default="en")
    prep_seconds = models.PositiveIntegerField(null=True, blank=True)
    response_seconds = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    rubric_version = models.ForeignKey(RubricVersion, on_delete=PROTECT, related_name="blueprint_slots")

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("blueprint_version", "position"), name="unique_blueprint_slot_position"),
            models.UniqueConstraint(fields=("blueprint_version", "section_name"), name="unique_blueprint_slot_section"),
            models.CheckConstraint(condition=Q(position__gte=1), name="blueprint_slot_position_positive"),
            models.CheckConstraint(condition=Q(question_count__gte=1), name="blueprint_slot_question_count_positive"),
            models.CheckConstraint(condition=Q(response_seconds__gte=1), name="blueprint_slot_response_seconds_positive"),
            models.CheckConstraint(condition=Q(target_level_min__lte=F("target_level_max")), name="blueprint_slot_level_range_ordered"),
        ]

    def clean(self):
        super().clean()
        if (self.target_level_min in CEFR_ORDER and self.target_level_max in CEFR_ORDER
                and CEFR_ORDER[self.target_level_min] > CEFR_ORDER[self.target_level_max]):
            raise ValidationError({"target_level_max": "Mức tối đa phải bằng hoặc cao hơn mức tối thiểu."})

    def save(self, *args, **kwargs):
        if self.blueprint_version_id and BlueprintVersion.objects.filter(
            pk=self.blueprint_version_id
        ).exclude(status=BlueprintVersion.Status.DRAFT).exists():
            raise ValidationError("Không thể sửa slot của blueprint đã xuất bản.")
        if self.pk:
            previous = type(self).objects.select_related("blueprint_version").get(pk=self.pk)
            if previous.blueprint_version.status != BlueprintVersion.Status.DRAFT:
                raise ValidationError("Không thể sửa slot của blueprint đã xuất bản.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.blueprint_version.status != BlueprintVersion.Status.DRAFT:
            raise ValidationError("Không thể xóa slot của blueprint đã xuất bản.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.blueprint_version} · {self.section_name}"


class BlueprintSample(models.Model):
    blueprint_version = models.ForeignKey(BlueprintVersion, on_delete=PROTECT, related_name="samples")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="blueprint_samples"
    )
    topic = models.CharField(max_length=160)
    seed = models.PositiveBigIntegerField()
    blueprint_snapshot = models.JSONField()
    candidate_pool_snapshot = models.JSONField()
    exclusion_snapshot = models.JSONField()
    selected_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Snapshot đề mẫu là bất biến.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa snapshot đề mẫu.")


@receiver(pre_delete, sender=BlueprintSlot)
def prevent_locked_blueprint_slot_deletion(sender, instance, **kwargs):
    if instance.blueprint_version.status != BlueprintVersion.Status.DRAFT:
        raise ValidationError("Không thể xóa slot của blueprint đã xuất bản.")


@receiver(pre_delete, sender=BlueprintSample)
def prevent_blueprint_sample_deletion(sender, instance, **kwargs):
    raise ValidationError("Không thể xóa snapshot đề mẫu.")


@receiver(pre_delete, sender=BlueprintAuditEvent)
def prevent_blueprint_audit_deletion(sender, instance, **kwargs):
    raise ValidationError("Không thể xóa lịch sử blueprint.")


def practice_audio_upload_path(instance, _filename):
    return (
        f"practice-audio/{instance.attempt.student_id}/{instance.attempt_id}/"
        f"question-{instance.question_index}.{instance.audio_extension}"
    )


class PracticeAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "Đang làm"
        SUBMITTED = "submitted", "Đã nộp"

    class ScoringStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Chưa chấm"
        AI_PROCESSING = "ai_processing", "AI đang chấm"
        AI_DRAFT = "ai_draft", "AI nháp"
        FINAL = "final", "Đã duyệt điểm"
        FAILED = "failed", "AI chấm lỗi"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="practice_attempts")
    course = models.ForeignKey(Course, on_delete=PROTECT, related_name="practice_attempts")
    cefr_level = models.CharField(max_length=2, choices=CEFR_LEVELS)
    topic = models.CharField(max_length=120, blank=True)
    question_count = models.PositiveSmallIntegerField()
    response_seconds = models.PositiveSmallIntegerField()
    ai_model = models.CharField(max_length=100)
    questions = models.JSONField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    scoring_status = models.CharField(max_length=16, choices=ScoringStatus.choices, default=ScoringStatus.NOT_STARTED)
    ai_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ai_result = models.JSONField(default=dict, blank=True)
    ai_scored_at = models.DateTimeField(null=True, blank=True)
    scoring_error = models.TextField(blank=True)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_feedback = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_practice_attempts",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(condition=Q(question_count__gte=1), name="practice_question_count_positive"),
            models.CheckConstraint(condition=Q(response_seconds__gte=1), name="practice_response_seconds_positive"),
        ]

    def __str__(self):
        return f"{self.student} · {self.course.code} · {self.created_at:%Y-%m-%d %H:%M}"


class PracticeAnswer(models.Model):
    attempt = models.ForeignKey(PracticeAttempt, on_delete=PROTECT, related_name="answers")
    question_index = models.PositiveSmallIntegerField()
    audio = models.FileField(upload_to=practice_audio_upload_path)
    audio_extension = models.CharField(max_length=5)
    content_type = models.CharField(max_length=32)
    duration_seconds = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("question_index",)
        constraints = [
            models.UniqueConstraint(fields=("attempt", "question_index"), name="unique_practice_answer_per_question"),
            models.CheckConstraint(condition=Q(question_index__gte=1), name="practice_answer_index_positive"),
            models.CheckConstraint(condition=Q(duration_seconds__gte=1), name="practice_answer_duration_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.attempt.status != PracticeAttempt.Status.IN_PROGRESS:
            raise ValidationError("Bài luyện đã nộp, không thể thay đổi bản ghi.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Không thể xóa câu trả lời đã lưu.")


@receiver(m2m_changed, sender=QuestionVersion.tags.through)
def protect_locked_version_tags(sender, instance, action, **kwargs):
    if action in {"pre_add", "pre_remove", "pre_clear"} and instance.pk:
        if QuestionVersion.objects.filter(pk=instance.pk).exclude(status=QuestionVersion.Status.DRAFT).exists():
            raise ValidationError("Không thể đổi tag của phiên bản đã gửi duyệt.")


@receiver(pre_delete, sender=QuestionReview)
def prevent_question_review_deletion(sender, instance, **kwargs):
    raise ValidationError("Không thể xóa lịch sử duyệt.")
