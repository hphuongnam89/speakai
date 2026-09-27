from datetime import timedelta
from decimal import Decimal
from functools import wraps
import secrets

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.blueprints import InsufficientQuestionPool, sample_blueprint
from core.forms import (
    BlueprintSampleForm, BlueprintVersionForm, DemoAccountForm, ExamScoreForm, ExamStartForm,
    PracticeAnswerForm, PracticeCreateForm, QuestionImportForm, QuestionVersionForm, RubricVersionForm, PracticeReviewForm,
    ExamClaimForm,
)
from core.practice_ai import PracticeGenerationError, generate_practice_questions
from core.official_scoring import score_official_attempt
from core.models import (
    BlueprintAuditEvent, BlueprintSlot, BlueprintVersion, Course, CourseTeachingAssignment,
    ExamAnswer, ExamAttempt, ExamScoreDecision,
    CriterionLevelDescriptor, ExamBlueprint, PracticeAnswer, PracticeAttempt,
    Question, QuestionReview, QuestionVersion,
    Rubric, RubricAuditEvent, RubricCriterion, RubricVersion,
)


ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
ROLE_ADMIN = "admin"


def role_required(role):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            has_role = request.user.groups.filter(name=role).exists()
            if role == ROLE_ADMIN and request.user.is_superuser:
                has_role = True
            if not has_role:
                return HttpResponseForbidden("Tài khoản không có quyền truy cập chức năng này.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def home(request):
    return render(request, "core/home.html")


@login_required
def dashboard(request):
    if request.user.is_superuser or request.user.groups.filter(name=ROLE_ADMIN).exists():
        return redirect("dashboard_admin")
    if request.user.groups.filter(name=ROLE_TEACHER).exists():
        return redirect("dashboard_teacher")
    if request.user.groups.filter(name=ROLE_STUDENT).exists():
        return redirect("dashboard_student")
    return HttpResponseForbidden("Tài khoản chưa được gán vai trò. Vui lòng liên hệ quản trị viên.")


@role_required(ROLE_STUDENT)
def student_dashboard(request):
    courses = Course.objects.filter(
        is_active=True, enrollments__student=request.user,
    ).distinct()
    official_versions = BlueprintVersion.objects.filter(
        blueprint__course__in=courses, status=BlueprintVersion.Status.PUBLISHED,
    ).select_related("blueprint__course").order_by("blueprint__course__code", "-version")
    attempt_history = PracticeAttempt.objects.filter(student=request.user)
    attempts = attempt_history.select_related("course")[:3]
    return render(request, "core/dashboard_student.html", {
        "courses": courses,
        "official_versions": official_versions,
        "attempts": attempts,
        "attempts_total": attempt_history.count(),
    })


def practice_in_scope(user, attempt_id):
    return get_object_or_404(
        PracticeAttempt.objects.select_related("course", "student"), pk=attempt_id, student=user,
    )


def attempt_preflight_key(attempt_id):
    return f"speaking_preflight_done:{attempt_id}"


def has_attempt_preflight(request, attempt):
    return bool(request.session.get(attempt_preflight_key(attempt.pk)))


@role_required(ROLE_STUDENT)
def practice_create(request):
    courses = Course.objects.filter(is_active=True, enrollments__student=request.user).distinct()
    form = PracticeCreateForm(request.POST or None, courses=courses)
    generation_error = ""
    if request.method == "POST" and form.is_valid():
        request.session[f"speaking_preflight:{request.user.pk}"] = {
            "course_id": form.cleaned_data["course"].pk,
            "level": form.cleaned_data["level"],
            "topic": form.cleaned_data["topic"],
            "question_count": form.cleaned_data["question_count"],
            "response_seconds": form.cleaned_data["response_seconds"],
            "nonce": secrets.token_urlsafe(24),
            "created_at": timezone.now().timestamp(),
        }
        return redirect("practice_preflight")
    return render(request, "core/practice_create.html", {
        "form": form, "generation_error": generation_error, "has_courses": courses.exists(),
    }, status=503 if generation_error else 200)


@role_required(ROLE_STUDENT)
def practice_preflight(request):
    setup = request.session.get(f"speaking_preflight:{request.user.pk}")
    if not setup or timezone.now().timestamp() - setup.get("created_at", 0) > 1200:
        if setup and setup.get("attempt_id"):
            request.session.pop(f"speaking_preflight:{request.user.pk}", None)
            return redirect("practice_detail", attempt_id=setup["attempt_id"])
        return redirect("practice_create")
    courses = Course.objects.filter(is_active=True, enrollments__student=request.user)
    if not courses.filter(pk=setup["course_id"]).exists():
        return redirect("practice_create")
    if setup.get("attempt_id"):
        attempt = practice_in_scope(request.user, setup["attempt_id"])
        if attempt.status != PracticeAttempt.Status.IN_PROGRESS:
            return redirect("practice_detail", attempt_id=attempt.pk)
    return render(request, "core/practice_preflight.html", {
        "setup": setup, "network_probe_url": reverse("network_probe"),
        "preflight_complete_url": reverse("practice_preflight_complete"),
        "practice_start_url": reverse("practice_start"),
    })


@role_required(ROLE_STUDENT)
def practice_preflight_complete(request):
    if request.method != "POST":
        return HttpResponseForbidden("Xác nhận kiểm tra thiết bị cần POST.")
    setup = request.session.get(f"speaking_preflight:{request.user.pk}")
    if (
        not setup
        or timezone.now().timestamp() - setup.get("created_at", 0) > 1200
        or request.POST.get("nonce") != setup.get("nonce")
    ):
        return JsonResponse({"error": "Phiên kiểm tra đã hết hạn. Hãy bắt đầu lại."}, status=400)
    try:
        speed_bps = int(request.POST.get("speed_bps", "0"))
        latency_ms = int(request.POST.get("latency_ms", "-1"))
    except ValueError:
        return JsonResponse({"error": "Kết quả kiểm tra không hợp lệ."}, status=400)
    if (
        request.POST.get("mic_verified") != "1"
        or request.POST.get("playback_confirmed") != "1"
        or speed_bps < 32_768
        or not 0 <= latency_ms <= 2000
    ):
        return JsonResponse({"error": "Cần kiểm tra micro và đạt ngưỡng kết nối trước khi tiếp tục."}, status=400)
    setup["verified_at"] = timezone.now().timestamp()
    setup["speed_bps"] = speed_bps
    setup["latency_ms"] = latency_ms
    request.session[f"speaking_preflight:{request.user.pk}"] = setup
    return JsonResponse({"ready": True})


@role_required(ROLE_STUDENT)
def network_probe(request):
    if request.method != "POST":
        return HttpResponseForbidden("Kiểm tra kết nối cần POST.")
    content_length = request.META.get("CONTENT_LENGTH", "0")
    if content_length not in {"0", "262144"}:
        return JsonResponse({"error": "Gói kiểm tra không hợp lệ."}, status=400)
    body = request.body
    if len(body) == 0:
        return HttpResponse(status=204, headers={"Cache-Control": "no-store, max-age=0"})
    if len(body) != 262_144:
        return JsonResponse({"error": "Gói kiểm tra không hợp lệ."}, status=400)
    response = HttpResponse(body, content_type="application/octet-stream")
    response["Cache-Control"] = "no-store, max-age=0"
    return response


@role_required(ROLE_STUDENT)
def practice_start(request):
    if request.method != "POST":
        return HttpResponseForbidden("Bắt đầu bài luyện cần POST.")
    key = f"speaking_preflight:{request.user.pk}"
    setup = request.session.get(key)
    if not setup or not setup.get("verified_at") or timezone.now().timestamp() - setup["verified_at"] > 1200:
        return redirect("practice_preflight")
    if setup.get("attempt_id"):
        attempt = practice_in_scope(request.user, setup["attempt_id"])
        if attempt.status != PracticeAttempt.Status.IN_PROGRESS:
            return redirect("practice_detail", attempt_id=attempt.pk)
        request.session[attempt_preflight_key(attempt.pk)] = timezone.now().timestamp()
        del request.session[key]
        return redirect("practice_detail", attempt_id=attempt.pk)
    course = get_object_or_404(
        Course.objects.filter(is_active=True, enrollments__student=request.user), pk=setup["course_id"],
    )
    try:
        generated = generate_practice_questions(
            level=setup["level"], topic=setup["topic"], question_count=setup["question_count"],
        )
    except PracticeGenerationError as exc:
        del request.session[key]
        messages.error(request, str(exc))
        return redirect("practice_create")
    attempt = PracticeAttempt.objects.create(
        student=request.user, course=course, cefr_level=setup["level"], topic=generated["topic"],
        question_count=len(generated["questions"]), response_seconds=setup["response_seconds"],
        ai_model=generated["model"], questions=generated["questions"],
    )
    request.session[attempt_preflight_key(attempt.pk)] = timezone.now().timestamp()
    del request.session[key]
    return redirect("practice_detail", attempt_id=attempt.pk)


@role_required(ROLE_STUDENT)
def practice_detail(request, attempt_id):
    attempt = practice_in_scope(request.user, attempt_id)
    if attempt.status == PracticeAttempt.Status.IN_PROGRESS and not has_attempt_preflight(request, attempt):
        request.session[f"speaking_preflight:{request.user.pk}"] = {
            "course_id": attempt.course_id, "level": attempt.cefr_level,
            "topic": attempt.topic, "question_count": attempt.question_count,
            "response_seconds": attempt.response_seconds, "attempt_id": attempt.pk,
            "nonce": secrets.token_urlsafe(24), "created_at": timezone.now().timestamp(),
        }
        return redirect("practice_preflight")
    answers = {answer.question_index: answer for answer in attempt.answers.all()}
    items = [
        {"index": index, "question": question, "answer": answers.get(index)}
        for index, question in enumerate(attempt.questions, start=1)
    ]
    return render(request, "core/practice_detail.html", {
        "attempt": attempt, "items": items, "saved_count": len(answers),
    })


@role_required(ROLE_STUDENT)
def practice_answer_upload(request, attempt_id):
    if request.method != "POST":
        return HttpResponseForbidden("Lưu câu trả lời cần POST.")
    attempt = practice_in_scope(request.user, attempt_id)
    if attempt.status != PracticeAttempt.Status.IN_PROGRESS:
        return HttpResponseForbidden("Bài luyện đã nộp.")
    if not has_attempt_preflight(request, attempt):
        messages.error(request, "Hoàn tất kiểm tra micro và kết nối trước khi lưu câu trả lời.")
        return redirect("practice_detail", attempt_id=attempt.pk)
    form = PracticeAnswerForm(request.POST, request.FILES)
    if form.is_valid():
        index = form.cleaned_data["question_index"]
        duration = form.cleaned_data["duration_seconds"]
        if index > len(attempt.questions) or duration > attempt.response_seconds:
            return HttpResponseForbidden("Câu hỏi hoặc thời lượng ghi âm không hợp lệ.")
        if attempt.answers.filter(question_index=index).exists():
            messages.error(request, "Câu này đã được lưu; không thể ghi đè bản ghi trong lượt luyện này.")
        else:
            PracticeAnswer.objects.create(
                attempt=attempt, question_index=index, audio=form.cleaned_data["audio"],
                audio_extension=form.cleaned_data["audio_extension"],
                content_type=form.cleaned_data["audio_mime"], duration_seconds=duration,
            )
            messages.success(request, f"Đã lưu bản ghi câu {index}.")
    else:
        messages.error(request, "Không lưu được bản ghi: " + "; ".join(
            error for errors in form.errors.values() for error in errors
        ))
    return redirect("practice_detail", attempt_id=attempt.pk)


@role_required(ROLE_STUDENT)
def practice_submit(request, attempt_id):
    if request.method != "POST":
        return HttpResponseForbidden("Nộp bài cần POST.")
    attempt = practice_in_scope(request.user, attempt_id)
    if attempt.status != PracticeAttempt.Status.IN_PROGRESS:
        return HttpResponseForbidden("Bài luyện đã nộp.")
    if not has_attempt_preflight(request, attempt):
        messages.error(request, "Hoàn tất kiểm tra micro và kết nối trước khi nộp bài.")
        return redirect("practice_detail", attempt_id=attempt.pk)
    if attempt.answers.count() != len(attempt.questions):
        messages.error(request, "Hãy lưu bản ghi cho tất cả câu hỏi trước khi nộp bài.")
        return redirect("practice_detail", attempt_id=attempt.pk)
    attempt.status = PracticeAttempt.Status.SUBMITTED
    attempt.scoring_status = PracticeAttempt.ScoringStatus.AI_PROCESSING
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=("status", "scoring_status", "submitted_at"))
    request.session.pop(attempt_preflight_key(attempt.pk), None)
    from core.tasks import score_practice_attempt
    score_practice_attempt.delay(attempt.pk)
    messages.success(request, "Đã nộp bài. AI đang chấm sơ bộ; giảng viên sẽ duyệt điểm cuối.")
    return redirect("practice_detail", attempt_id=attempt.pk)


@login_required
def practice_review(request, attempt_id):
    if not (is_content_admin(request.user) or request.user.groups.filter(name=ROLE_TEACHER).exists()):
        return HttpResponseForbidden("Chức năng này dành cho giảng viên và quản trị viên.")
    attempts = PracticeAttempt.objects.select_related("course", "student").prefetch_related("answers")
    if not is_content_admin(request.user):
        attempts = attempts.filter(
            course__teaching_assignments__teacher=request.user,
            course__teaching_assignments__is_active=True,
        )
    attempt = get_object_or_404(attempts, pk=attempt_id)
    if request.method == "POST":
        form = PracticeReviewForm(request.POST)
        if form.is_valid():
            attempt.final_score = form.cleaned_data["score"]
            attempt.final_feedback = form.cleaned_data["feedback"].strip()
            attempt.reviewed_by = request.user
            attempt.reviewed_at = timezone.now()
            attempt.scoring_status = PracticeAttempt.ScoringStatus.FINAL
            attempt.save(update_fields=("final_score", "final_feedback", "reviewed_by", "reviewed_at", "scoring_status"))
            messages.success(request, "Đã duyệt và công bố điểm cuối cho sinh viên.")
            return redirect("practice_review", attempt_id=attempt.pk)
    else:
        form = PracticeReviewForm(initial={"score": attempt.final_score or attempt.ai_score, "feedback": attempt.final_feedback})
    answers = {answer.question_index: answer for answer in attempt.answers.all()}
    items = [
        {"index": index, "question": question, "answer": answers.get(index)}
        for index, question in enumerate(attempt.questions, start=1)
    ]
    return render(request, "core/practice_review.html", {"attempt": attempt, "items": items, "form": form})


@login_required
def practice_answer_audio(request, answer_id):
    answer = get_object_or_404(PracticeAnswer.objects.select_related("attempt", "attempt__course"), pk=answer_id)
    attempt = answer.attempt
    allowed = attempt.student_id == request.user.pk or is_content_admin(request.user) or (
        request.user.groups.filter(name=ROLE_TEACHER).exists()
        and CourseTeachingAssignment.objects.filter(
            teacher=request.user, course_id=attempt.course_id, is_active=True,
        ).exists()
    )
    if not allowed:
        return HttpResponseForbidden("Bạn không có quyền nghe bản ghi này.")
    return FileResponse(answer.audio.open("rb"), content_type=answer.content_type)


@role_required(ROLE_TEACHER)
def teacher_dashboard(request):
    courses = Course.objects.filter(
        teaching_assignments__teacher=request.user, teaching_assignments__is_active=True,
    )
    attempts = PracticeAttempt.objects.filter(course__in=courses).select_related(
        "student", "course",
    ).prefetch_related("answers")[:10]
    return render(request, "core/dashboard_teacher.html", {"practice_attempts": attempts})


@role_required(ROLE_ADMIN)
def admin_dashboard(request):
    attempts = PracticeAttempt.objects.select_related("student", "course").prefetch_related("answers")[:10]
    accounts = list(
        get_user_model().objects.filter(username__startswith="demo-")
        .exclude(is_staff=True).exclude(is_superuser=True).prefetch_related("groups").order_by("username")
    )
    for account in accounts:
        account.role_label = demo_role_label(account)
    return render(request, "core/dashboard_admin.html", {
        "practice_attempts": attempts,
        "demo_accounts": accounts[:5],
        "demo_account_total": len(accounts),
    })


def demo_role_label(account):
    labels = {"student": "Sinh viên", "teacher": "Giảng viên", "admin": "Quản trị viên"}
    roles = {group.name for group in account.groups.all()}
    return next((label for role, label in labels.items() if role in roles), "Chưa gán vai trò")


@role_required(ROLE_ADMIN)
def demo_accounts(request):
    User = get_user_model()
    base_queryset = User.objects.filter(username__startswith="demo-").exclude(
        is_staff=True,
    ).exclude(is_superuser=True)
    accounts = base_queryset.prefetch_related("groups").order_by("username")
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")
    if query:
        accounts = accounts.filter(Q(username__icontains=query) | Q(email__icontains=query))
    if role in {ROLE_STUDENT, ROLE_TEACHER, ROLE_ADMIN}:
        accounts = accounts.filter(groups__name=role).distinct()
    if status == "active":
        accounts = accounts.filter(is_active=True)
    elif status == "inactive":
        accounts = accounts.filter(is_active=False)
    accounts = list(accounts)
    for account in accounts:
        account.role_label = demo_role_label(account)
    return render(request, "core/demo_accounts.html", {
        "accounts": accounts,
        "accounts_total": base_queryset.count(),
        "query": query,
        "selected_role": role,
        "selected_status": status,
    })


@role_required(ROLE_ADMIN)
def demo_account_create(request):
    form = DemoAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                is_active=form.cleaned_data["is_active"],
            )
            user.groups.add(Group.objects.get_or_create(name=form.cleaned_data["role"])[0])
        messages.success(request, f"Tài khoản {user.username} đã được tạo.")
        return redirect("demo_accounts")
    return render(request, "core/demo_account_form.html", {"form": form, "creating": True})


@role_required(ROLE_ADMIN)
def demo_account_edit(request, username):
    account = get_object_or_404(
        get_user_model().objects.filter(username__startswith="demo-", is_staff=False, is_superuser=False),
        username=username,
    )
    form = DemoAccountForm(request.POST or None, instance=account)
    if request.method == "POST" and form.is_valid():
        role = form.cleaned_data["role"]
        active = form.cleaned_data["is_active"]
        if account.pk == request.user.pk and (role != ROLE_ADMIN or not active):
            form.add_error(None, "Không thể bỏ vai trò quản trị hoặc khóa chính tài khoản đang đăng nhập.")
        elif role != ROLE_ADMIN or not active:
            remaining_admin = get_user_model().objects.filter(is_active=True).filter(
                Q(is_superuser=True) | Q(groups__name=ROLE_ADMIN),
            ).exclude(pk=account.pk).exists()
            if not remaining_admin:
                form.add_error(None, "Cần giữ ít nhất một tài khoản quản trị đang hoạt động.")
        if form.is_valid():
            with transaction.atomic():
                account.email = form.cleaned_data["email"]
                account.is_active = active
                account.save(update_fields=["email", "is_active"])
                password = form.cleaned_data["password"]
                if password:
                    account.set_password(password)
                    account.save(update_fields=["password"])
                managed_groups = list(Group.objects.filter(name__in=[ROLE_STUDENT, ROLE_TEACHER, ROLE_ADMIN]))
                if managed_groups:
                    account.groups.remove(*managed_groups)
                account.groups.add(Group.objects.get_or_create(name=role)[0])
            messages.success(request, f"Tài khoản {account.username} đã được cập nhật.")
            return redirect("demo_accounts")
    return render(request, "core/demo_account_form.html", {"form": form, "account": account, "creating": False})


def is_content_admin(user):
    return user.is_superuser or user.groups.filter(name=ROLE_ADMIN).exists()


def content_staff_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not (is_content_admin(request.user) or request.user.groups.filter(name=ROLE_TEACHER).exists()):
            return HttpResponseForbidden("Tài khoản không có quyền truy cập chức năng này.")
        return view(request, *args, **kwargs)
    return wrapped


def manageable_courses(user, active_only=False):
    courses = Course.objects.all()
    if active_only:
        courses = courses.filter(is_active=True)
    if is_content_admin(user):
        return courses
    return courses.filter(teaching_assignments__teacher=user, teaching_assignments__is_active=True).distinct()


def version_in_scope(user, version_id):
    versions = QuestionVersion.objects.select_related("question", "question__course", "created_by")
    if not is_content_admin(user):
        versions = versions.filter(
            question__course__teaching_assignments__teacher=user,
            question__course__teaching_assignments__is_active=True,
        )
    return get_object_or_404(versions, pk=version_id)


@content_staff_required
def question_bank(request):
    courses = manageable_courses(request.user)
    all_versions = QuestionVersion.objects.filter(question__course__in=courses)
    versions = all_versions.select_related("question", "question__course")
    search = request.GET.get("q", "").strip()
    course_id = request.GET.get("course", "")
    task_type = request.GET.get("task_type", "")
    level = request.GET.get("level", "")
    status = request.GET.get("status", "")
    if search:
        versions = versions.filter(
            Q(prompt_text__icontains=search) | Q(topic__icontains=search)
            | Q(source_reference__icontains=search)
        )
    if course_id:
        versions = versions.filter(question__course_id=course_id) if course_id.isdecimal() else versions.none()
    if task_type:
        versions = versions.filter(task_type=task_type)
    if level:
        versions = versions.filter(Q(target_level_min__lte=level, target_level_max__gte=level))
    if status:
        versions = versions.filter(status=status)
    versions = versions.order_by("question__course__code", "question_id", "-version")
    page = Paginator(versions, 20).get_page(request.GET.get("page"))
    status_labels = {
        QuestionVersion.Status.DRAFT: "Bản nháp",
        QuestionVersion.Status.IN_REVIEW: "Chờ duyệt",
        QuestionVersion.Status.APPROVED: "Đã duyệt",
        QuestionVersion.Status.RETIRED: "Ngừng dùng",
    }
    for version in page.object_list:
        version.status_label = status_labels[version.status]
        version.task_type_label = version.task_type.replace("_", " ").title()
    counts = {choice.value: all_versions.filter(status=choice.value).count()
              for choice in QuestionVersion.Status}
    task_types = all_versions.exclude(task_type="").values_list(
        "task_type", flat=True
    ).distinct().order_by("task_type")
    return render(request, "core/question_bank.html", {
        "versions": page.object_list,
        "page_obj": page,
        "courses": courses,
        "search": search,
        "selected_course": course_id,
        "selected_task_type": task_type,
        "selected_level": level,
        "selected_status": status,
        "task_types": [(item, item.replace("_", " ").title()) for item in task_types],
        "levels": ("A1", "A2", "B1", "B2", "C1", "C2"),
        "total_count": all_versions.count(),
        "counts": counts,
        "status_choices": (
            (QuestionVersion.Status.DRAFT, "Bản nháp"),
            (QuestionVersion.Status.IN_REVIEW, "Chờ duyệt"),
            (QuestionVersion.Status.APPROVED, "Đã duyệt"),
            (QuestionVersion.Status.RETIRED, "Ngừng dùng"),
        ),
    })


@content_staff_required
def question_create(request):
    courses = manageable_courses(request.user, active_only=True)
    course = None
    form = QuestionVersionForm(request.POST or None)
    if request.method == "POST":
        course = courses.filter(pk=request.POST.get("course")).first()
        if not course:
            form.add_error(None, "Học phần không hợp lệ hoặc chưa được phân công.")
        elif form.is_valid():
            try:
                with transaction.atomic():
                    question = Question.objects.create(course=course, created_by=request.user)
                    version = form.save(commit=False)
                    version.question = question
                    version.created_by = request.user
                    version.version = 1
                    version.full_clean()
                    version.save()
                    form.save_m2m()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect("question_detail", question_id=question.pk)
    return render(request, "core/question_form.html", {"form": form, "courses": courses, "course": course})


@content_staff_required
def question_import(request):
    courses = manageable_courses(request.user, active_only=True)
    form = QuestionImportForm(request.POST or None)
    course = courses.filter(pk=request.POST.get("course")).first() if request.method == "POST" else courses.first()
    if request.method == "POST" and form.is_valid():
        if not course:
            form.add_error(None, "Học phần không hợp lệ hoặc chưa được phân công.")
        else:
            payload = form.cleaned_data["payload"]
            if not isinstance(payload, list) or not payload or len(payload) > 200:
                form.add_error("payload", "Payload phải là danh sách 1–200 câu hỏi.")
            else:
                required = {"language", "task_type", "topic", "prompt_text", "target_level_min", "target_level_max", "prep_seconds", "response_seconds", "source_reference", "exam_metadata"}
                try:
                    with transaction.atomic():
                        for index, item in enumerate(payload, start=1):
                            if not isinstance(item, dict) or not required.issubset(item):
                                raise ValidationError(f"Câu {index}: thiếu trường bắt buộc.")
                            if not isinstance(item["exam_metadata"], dict) or not item["exam_metadata"]:
                                raise ValidationError(f"Câu {index}: exam_metadata phải là object JSON không rỗng.")
                            question = Question.objects.create(course=course, created_by=request.user)
                            version = QuestionVersion(
                                question=question, version=1, created_by=request.user,
                                language=item["language"], task_type=item["task_type"], topic=item["topic"],
                                target_level_min=item["target_level_min"], target_level_max=item["target_level_max"],
                                prompt_text=item["prompt_text"], candidate_instructions=item.get("candidate_instructions", ""),
                                prep_seconds=item["prep_seconds"], response_seconds=item["response_seconds"],
                                required_points=item.get("required_points", []), optional_prompts=item.get("optional_prompts", []),
                                allowed_alternatives=item.get("allowed_alternatives", []), criterion_refs=item.get("criterion_refs", []),
                                source_reference=item["source_reference"], source_notes=item.get("source_notes", ""),
                                exam_metadata=item["exam_metadata"],
                            )
                            version.full_clean()
                            version.save()
                except (ValidationError, TypeError, ValueError) as exc:
                    form.add_error(None, exc)
                else:
                    messages.success(request, f"Đã nhập {len(payload)} câu hỏi ở trạng thái bản nháp. Hãy gửi duyệt từng phiên bản.")
                    return redirect("question_bank")
    return render(request, "core/question_import.html", {"form": form, "courses": courses, "course": course})


@content_staff_required
def question_detail(request, question_id):
    courses = manageable_courses(request.user)
    question = get_object_or_404(
        Question.objects.filter(course__in=courses).select_related("course").prefetch_related(
            "versions__tags", "versions__reviews__reviewer"
        ), pk=question_id,
    )
    can_review = is_content_admin(request.user) or CourseTeachingAssignment.objects.filter(
        course=question.course, teacher=request.user, is_active=True
    ).exists()
    return render(request, "core/question_detail.html", {
        "question": question, "can_review": can_review, "is_admin": is_content_admin(request.user),
    })


@content_staff_required
def question_edit(request, version_id):
    version = version_in_scope(request.user, version_id)
    if version.status != QuestionVersion.Status.DRAFT:
        return HttpResponseForbidden("Chỉ phiên bản nháp mới được chỉnh sửa.")
    form = QuestionVersionForm(request.POST or None, instance=version)
    if request.method == "POST" and form.is_valid():
        try:
            updated = form.save(commit=False)
            updated.full_clean()
            updated.save()
            form.save_m2m()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("question_detail", question_id=version.question_id)
    return render(request, "core/question_form.html", {"form": form, "edit_version": version})


@content_staff_required
def question_submit_review(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    version = version_in_scope(request.user, version_id)
    if version.status != QuestionVersion.Status.DRAFT:
        return HttpResponseForbidden("Chỉ bản nháp mới gửi duyệt được.")
    try:
        version.full_clean()
        version.status = QuestionVersion.Status.IN_REVIEW
        version.save()
    except ValidationError as exc:
        return render(request, "core/question_action_error.html", {"error": exc}, status=400)
    return redirect("question_detail", question_id=version.question_id)


@content_staff_required
def question_review(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    version = version_in_scope(request.user, version_id)
    if version.status != QuestionVersion.Status.IN_REVIEW:
        return HttpResponseForbidden("Phiên bản không ở trạng thái chờ duyệt.")
    if version.created_by_id == request.user.pk:
        return HttpResponseForbidden("Người tạo không thể tự duyệt phiên bản.")
    decision = request.POST.get("decision")
    note = request.POST.get("note", "").strip()
    if decision not in QuestionReview.Decision.values or (decision == QuestionReview.Decision.CHANGES_REQUESTED and not note):
        return render(request, "core/question_action_error.html", {
            "error": "Lựa chọn không hợp lệ; yêu cầu chỉnh sửa phải có lý do.",
        }, status=400)
    try:
        with transaction.atomic():
            review = QuestionReview(
                question_version=version, reviewer=request.user, decision=decision, note=note,
            )
            review.full_clean()
            review.save()
            version.status = (
                QuestionVersion.Status.APPROVED
                if decision == QuestionReview.Decision.APPROVED
                else QuestionVersion.Status.DRAFT
            )
            version.save()
    except ValidationError as exc:
        return render(request, "core/question_action_error.html", {"error": exc}, status=400)
    return redirect("question_detail", question_id=version.question_id)


@content_staff_required
def question_new_revision(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    source = version_in_scope(request.user, version_id)
    if source.status != QuestionVersion.Status.APPROVED:
        return HttpResponseForbidden("Chỉ có thể tạo phiên bản mới từ câu đã duyệt.")
    with transaction.atomic():
        question = Question.objects.select_for_update().get(pk=source.question_id)
        last_version = question.versions.order_by("-version").values_list("version", flat=True).first()
        duplicate = QuestionVersion.objects.create(
            question=question, version=last_version + 1, created_by=request.user,
            language=source.language, task_type=source.task_type, topic=source.topic,
            target_level_min=source.target_level_min, target_level_max=source.target_level_max,
            prompt_text=source.prompt_text, candidate_instructions=source.candidate_instructions,
            prep_seconds=source.prep_seconds, response_seconds=source.response_seconds,
            required_points=source.required_points, optional_prompts=source.optional_prompts,
            allowed_alternatives=source.allowed_alternatives, criterion_refs=source.criterion_refs,
            source_reference=source.source_reference, source_notes=source.source_notes,
            exam_metadata=source.exam_metadata,
        )
        duplicate.tags.set(source.tags.all())
    return redirect("question_edit", version_id=duplicate.pk)


@content_staff_required
def question_retire(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    version = version_in_scope(request.user, version_id)
    if not is_content_admin(request.user):
        return HttpResponseForbidden("Chỉ quản trị viên mới được ngừng sử dụng câu hỏi đã duyệt.")
    if version.status != QuestionVersion.Status.APPROVED:
        return HttpResponseForbidden("Chỉ câu đã duyệt mới được ngừng sử dụng.")
    version.status = QuestionVersion.Status.RETIRED
    version.save()
    return redirect("question_detail", question_id=version.question_id)


def rubric_version_in_scope(user, version_id):
    versions = RubricVersion.objects.select_related("rubric", "rubric__course", "created_by")
    if not is_content_admin(user):
        versions = versions.filter(
            rubric__course__teaching_assignments__teacher=user,
            rubric__course__teaching_assignments__is_active=True,
        )
    return get_object_or_404(versions, pk=version_id)


def save_rubric_criteria(version, payload):
    version.criteria.all().delete()
    for position, item in enumerate(payload, start=1):
        criterion = RubricCriterion.objects.create(
            rubric_version=version,
            position=position,
            name=item["name"].strip(),
            description=item.get("description", "").strip(),
            weight=item["weight"],
            signal=item["signal"],
            bands=item.get("bands") or {},
            max_points=item.get("max_points"),
        )
        CriterionLevelDescriptor.objects.bulk_create([
            CriterionLevelDescriptor(
                criterion=criterion, level=descriptor["level"], text=descriptor["text"].strip(),
            )
            for descriptor in item["descriptors"]
        ])


@content_staff_required
def rubric_bank(request):
    courses = manageable_courses(request.user)
    rubrics = Rubric.objects.filter(course__in=courses).select_related("course").prefetch_related(
        "versions__criteria__descriptors", "versions__audit_events__actor"
    )
    return render(request, "core/rubric_bank.html", {"rubrics": rubrics, "courses": courses})


@content_staff_required
def rubric_create(request):
    courses = manageable_courses(request.user, active_only=True)
    form = RubricVersionForm(request.POST or None)
    selected_course = None
    if request.method == "POST":
        selected_course = courses.filter(pk=request.POST.get("course")).first()
        if selected_course is None:
            form.add_error(None, "Học phần không hợp lệ hoặc chưa được phân công.")
        elif form.is_valid():
            try:
                with transaction.atomic():
                    rubric = Rubric.objects.create(course=selected_course, created_by=request.user)
                    version = form.save(commit=False)
                    version.rubric = rubric
                    version.version = 1
                    version.created_by = request.user
                    version.full_clean()
                    version.save()
                    save_rubric_criteria(version, form.cleaned_data["criteria_payload"])
                    snapshot = version.content_snapshot()
                    RubricAuditEvent.objects.create(
                        rubric_version=version, actor=request.user,
                        action=RubricAuditEvent.Action.CREATED, after_snapshot=snapshot,
                    )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect("rubric_detail", rubric_id=rubric.pk)
    return render(request, "core/rubric_form.html", {
        "form": form, "courses": courses, "selected_course": selected_course,
    })


@content_staff_required
def rubric_detail(request, rubric_id):
    rubric = get_object_or_404(
        Rubric.objects.filter(course__in=manageable_courses(request.user)).select_related("course").prefetch_related(
            "versions__criteria__descriptors", "versions__audit_events__actor"
        ), pk=rubric_id,
    )
    return render(request, "core/rubric_detail.html", {
        "rubric": rubric, "is_admin": is_content_admin(request.user),
    })


@content_staff_required
def rubric_edit(request, version_id):
    version = rubric_version_in_scope(request.user, version_id)
    if version.status != RubricVersion.Status.DRAFT:
        return HttpResponseForbidden("Chỉ rubric nháp mới được chỉnh sửa.")
    form = RubricVersionForm(instance=version)
    if request.method == "POST":
        try:
            with transaction.atomic():
                version = RubricVersion.objects.select_for_update().get(pk=version.pk)
                if version.status != RubricVersion.Status.DRAFT:
                    return HttpResponseForbidden("Chỉ rubric nháp mới được chỉnh sửa.")
                form = RubricVersionForm(request.POST, instance=version)
                if not form.is_valid():
                    return render(request, "core/rubric_form.html", {"form": form, "edit_version": version})
                before = version.content_snapshot()
                updated = form.save(commit=False)
                updated.full_clean()
                updated.save()
                save_rubric_criteria(updated, form.cleaned_data["criteria_payload"])
                after = updated.content_snapshot()
                RubricAuditEvent.objects.create(
                    rubric_version=updated, actor=request.user,
                    action=RubricAuditEvent.Action.UPDATED,
                    before_snapshot=before, after_snapshot=after,
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("rubric_detail", rubric_id=version.rubric_id)
    return render(request, "core/rubric_form.html", {"form": form, "edit_version": version})


@content_staff_required
def rubric_publish(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    with transaction.atomic():
        version = rubric_version_in_scope(request.user, version_id)
        version = RubricVersion.objects.select_for_update().get(pk=version.pk)
        if version.status != RubricVersion.Status.DRAFT:
            return HttpResponseForbidden("Chỉ rubric nháp mới được xuất bản.")
        try:
            version.validate_for_publication()
        except ValidationError as exc:
            return render(request, "core/question_action_error.html", {
                "error": exc,
            }, status=400)
        try:
            version.full_clean()
        except ValidationError as exc:
            return render(request, "core/question_action_error.html", {"error": exc}, status=400)
        before = {"status": version.status, **version.content_snapshot()}
        version.status = RubricVersion.Status.PUBLISHED
        version.published_at = timezone.now()
        version.save()
        RubricAuditEvent.objects.create(
            rubric_version=version, actor=request.user,
            action=RubricAuditEvent.Action.PUBLISHED,
            before_snapshot=before,
            after_snapshot={"status": version.status, **version.content_snapshot()},
        )
    return redirect("rubric_detail", rubric_id=version.rubric_id)


@content_staff_required
def rubric_new_revision(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    with transaction.atomic():
        source = rubric_version_in_scope(request.user, version_id)
        source = RubricVersion.objects.select_for_update().get(pk=source.pk)
        if source.status != RubricVersion.Status.PUBLISHED:
            return HttpResponseForbidden("Chỉ rubric đã xuất bản mới tạo được phiên bản kế tiếp.")
        rubric = Rubric.objects.select_for_update().get(pk=source.rubric_id)
        number = rubric.versions.order_by("-version").values_list("version", flat=True).first() + 1
        revision = RubricVersion.objects.create(
            rubric=rubric, version=number, created_by=request.user,
            title=source.title, section_name=source.section_name, task_type=source.task_type,
            target_level_min=source.target_level_min, target_level_max=source.target_level_max,
            source_reference=source.source_reference, source_notes=source.source_notes,
        )
        payload = source.content_snapshot()["criteria"]
        save_rubric_criteria(revision, payload)
        snapshot = revision.content_snapshot()
        RubricAuditEvent.objects.create(
            rubric_version=revision, actor=request.user,
            action=RubricAuditEvent.Action.REVISION_CREATED,
            before_snapshot={"source_version": source.version, "source_status": source.status, **snapshot},
            after_snapshot=snapshot,
        )
    return redirect("rubric_edit", version_id=revision.pk)


@content_staff_required
def rubric_retire(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    if not is_content_admin(request.user):
        return HttpResponseForbidden("Chỉ quản trị viên mới được ngừng sử dụng rubric.")
    with transaction.atomic():
        version = rubric_version_in_scope(request.user, version_id)
        version = RubricVersion.objects.select_for_update().get(pk=version.pk)
        if version.status != RubricVersion.Status.PUBLISHED:
            return HttpResponseForbidden("Chỉ rubric đã xuất bản mới được ngừng sử dụng.")
        before = {"status": version.status, **version.content_snapshot()}
        version.status = RubricVersion.Status.RETIRED
        version.save()
        RubricAuditEvent.objects.create(
            rubric_version=version, actor=request.user,
            action=RubricAuditEvent.Action.RETIRED,
            before_snapshot=before,
            after_snapshot={"status": version.status, **version.content_snapshot()},
        )
    return redirect("rubric_detail", rubric_id=version.rubric_id)


def allowed_blueprint_rubrics(course_id):
    return RubricVersion.objects.filter(
        rubric__course_id=course_id, status=RubricVersion.Status.PUBLISHED
    ).select_related("rubric").order_by("rubric__course__code", "section_name", "task_type", "-version")


def blueprint_version_in_scope(user, version_id):
    versions = BlueprintVersion.objects.select_related("blueprint", "blueprint__course", "created_by")
    if not is_content_admin(user):
        versions = versions.filter(
            blueprint__course__teaching_assignments__teacher=user,
            blueprint__course__teaching_assignments__is_active=True,
        )
    return get_object_or_404(versions, pk=version_id)


def blueprint_in_scope(user, blueprint_id):
    return get_object_or_404(
        ExamBlueprint.objects.select_related("course").filter(
            course__in=manageable_courses(user)
        ), pk=blueprint_id,
    )


def save_blueprint_slots(version, payload):
    version.slots.all().delete()
    for position, data in enumerate(payload, start=1):
        slot = BlueprintSlot(
            blueprint_version=version,
            position=position,
            section_name=data["section_name"],
            task_type=data["task_type"],
            question_count=data["question_count"],
            target_level_min=data["target_level_min"],
            target_level_max=data["target_level_max"],
            language=data["language"],
            prep_seconds=data["prep_seconds"],
            response_seconds=data["response_seconds"],
            selection_rules=data.get("selection_rules") or {},
            max_points=data.get("max_points", "1"),
            rubric_version_id=data["rubric_version_id"],
        )
        slot.full_clean()
        slot.save()


@content_staff_required
def blueprint_bank(request):
    courses = manageable_courses(request.user)
    blueprints = ExamBlueprint.objects.filter(course__in=courses).select_related("course").prefetch_related(
        "versions__slots", "versions__audit_events__actor"
    )
    return render(request, "core/blueprint_bank.html", {"blueprints": blueprints})


@content_staff_required
def blueprint_create(request):
    courses = manageable_courses(request.user, active_only=True)
    selected_course = courses.filter(pk=request.POST.get("course")).first() if request.method == "POST" else None
    rubric_queryset = allowed_blueprint_rubrics(selected_course.pk) if selected_course else RubricVersion.objects.none()
    form = BlueprintVersionForm(
        request.POST or None, rubric_queryset=rubric_queryset,
    )
    if request.method == "POST":
        if not selected_course:
            form.add_error(None, "Học phần không hợp lệ hoặc chưa được phân công.")
        elif form.is_valid():
            try:
                with transaction.atomic():
                    blueprint = ExamBlueprint.objects.create(course=selected_course, created_by=request.user)
                    version = form.save(commit=False)
                    version.blueprint = blueprint
                    version.version = 1
                    version.created_by = request.user
                    version.full_clean()
                    version.save()
                    save_blueprint_slots(version, form.cleaned_data["slots_payload"])
                    snapshot = version.content_snapshot()
                    BlueprintAuditEvent.objects.create(
                        blueprint_version=version, actor=request.user,
                        action=BlueprintAuditEvent.Action.CREATED, after_snapshot=snapshot,
                    )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return redirect("blueprint_detail", blueprint_id=blueprint.pk)
    rubric_options = allowed_blueprint_rubrics(selected_course.pk) if selected_course else []
    return render(request, "core/blueprint_form.html", {
        "form": form, "courses": courses, "selected_course": selected_course,
        "rubric_options": rubric_options,
    })


@content_staff_required
def blueprint_detail(request, blueprint_id):
    blueprint = get_object_or_404(
        ExamBlueprint.objects.filter(course__in=manageable_courses(request.user)).select_related("course").prefetch_related(
            "versions__slots__rubric_version__rubric", "versions__samples__created_by",
            "versions__audit_events__actor",
        ), pk=blueprint_id,
    )
    topic_options = list(QuestionVersion.objects.filter(
        question__course=blueprint.course,
        status=QuestionVersion.Status.APPROVED,
        source_reference__gt="",
    ).order_by().values_list("topic", flat=True).distinct())
    return render(request, "core/blueprint_detail.html", {
        "blueprint": blueprint, "is_admin": is_content_admin(request.user),
        "topic_options": topic_options, "sample_form": BlueprintSampleForm(),
    })


@content_staff_required
def blueprint_edit(request, version_id):
    version = blueprint_version_in_scope(request.user, version_id)
    if version.status != BlueprintVersion.Status.DRAFT:
        return HttpResponseForbidden("Chỉ blueprint nháp mới được chỉnh sửa.")
    rubric_options = allowed_blueprint_rubrics(version.blueprint.course_id)
    form = BlueprintVersionForm(instance=version, rubric_queryset=rubric_options)
    if request.method == "POST":
        try:
            with transaction.atomic():
                version = BlueprintVersion.objects.select_for_update().get(pk=version.pk)
                if version.status != BlueprintVersion.Status.DRAFT:
                    return HttpResponseForbidden("Chỉ blueprint nháp mới được chỉnh sửa.")
                form = BlueprintVersionForm(request.POST, instance=version, rubric_queryset=rubric_options)
                if not form.is_valid():
                    return render(request, "core/blueprint_form.html", {
                        "form": form, "edit_version": version, "rubric_options": rubric_options,
                    })
                before = version.content_snapshot()
                updated = form.save(commit=False)
                updated.full_clean()
                updated.save()
                save_blueprint_slots(updated, form.cleaned_data["slots_payload"])
                after = updated.content_snapshot()
                BlueprintAuditEvent.objects.create(
                    blueprint_version=updated, actor=request.user,
                    action=BlueprintAuditEvent.Action.UPDATED,
                    before_snapshot=before, after_snapshot=after,
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("blueprint_detail", blueprint_id=version.blueprint_id)
    return render(request, "core/blueprint_form.html", {
        "form": form, "edit_version": version, "rubric_options": rubric_options,
    })


@content_staff_required
def blueprint_publish(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    with transaction.atomic():
        version = blueprint_version_in_scope(request.user, version_id)
        version = BlueprintVersion.objects.select_for_update().get(pk=version.pk)
        if version.status != BlueprintVersion.Status.DRAFT:
            return HttpResponseForbidden("Chỉ blueprint nháp mới được xuất bản.")
        before = {"status": version.status, **version.content_snapshot()}
        version.status = BlueprintVersion.Status.PUBLISHED
        version.published_at = timezone.now()
        try:
            version.full_clean()
            version.save()
        except ValidationError as exc:
            return render(request, "core/question_action_error.html", {"error": exc}, status=400)
        BlueprintAuditEvent.objects.create(
            blueprint_version=version, actor=request.user,
            action=BlueprintAuditEvent.Action.PUBLISHED,
            before_snapshot=before,
            after_snapshot={"status": version.status, **version.content_snapshot()},
        )
    return redirect("blueprint_detail", blueprint_id=version.blueprint_id)


@content_staff_required
def blueprint_new_revision(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    with transaction.atomic():
        source = blueprint_version_in_scope(request.user, version_id)
        source = BlueprintVersion.objects.select_for_update().get(pk=source.pk)
        if source.status != BlueprintVersion.Status.PUBLISHED:
            return HttpResponseForbidden("Chỉ blueprint đã xuất bản mới tạo được phiên bản kế tiếp.")
        blueprint = ExamBlueprint.objects.select_for_update().get(pk=source.blueprint_id)
        number = blueprint.versions.order_by("-version").values_list("version", flat=True).first() + 1
        revision = BlueprintVersion.objects.create(
            blueprint=blueprint, version=number, created_by=request.user,
            title=source.title, source_reference=source.source_reference, source_notes=source.source_notes,
        )
        payload = [
            {key: getattr(slot, key) for key in (
                "section_name", "task_type", "question_count", "target_level_min", "target_level_max",
                "language", "prep_seconds", "response_seconds",
            )} | {"selection_rules": slot.selection_rules, "max_points": str(slot.max_points), "rubric_version_id": slot.rubric_version_id}
            for slot in source.slots.all()
        ]
        save_blueprint_slots(revision, payload)
        snapshot = revision.content_snapshot()
        BlueprintAuditEvent.objects.create(
            blueprint_version=revision, actor=request.user,
            action=BlueprintAuditEvent.Action.REVISION_CREATED,
            before_snapshot={"source_version": source.version, "source_status": source.status, **snapshot},
            after_snapshot=snapshot,
        )
    return redirect("blueprint_edit", version_id=revision.pk)


@content_staff_required
def blueprint_retire(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Thao tác này cần POST.")
    if not is_content_admin(request.user):
        return HttpResponseForbidden("Chỉ quản trị viên mới được ngừng sử dụng blueprint.")
    with transaction.atomic():
        version = blueprint_version_in_scope(request.user, version_id)
        version = BlueprintVersion.objects.select_for_update().get(pk=version.pk)
        if version.status != BlueprintVersion.Status.PUBLISHED:
            return HttpResponseForbidden("Chỉ blueprint đã xuất bản mới được ngừng sử dụng.")
        before = {"status": version.status, **version.content_snapshot()}
        version.status = BlueprintVersion.Status.RETIRED
        version.save()
        BlueprintAuditEvent.objects.create(
            blueprint_version=version, actor=request.user,
            action=BlueprintAuditEvent.Action.RETIRED,
            before_snapshot=before,
            after_snapshot={"status": version.status, **version.content_snapshot()},
        )
    return redirect("blueprint_detail", blueprint_id=version.blueprint_id)


@content_staff_required
def blueprint_sample(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Tạo sample cần POST.")
    version = blueprint_version_in_scope(request.user, version_id)
    form = BlueprintSampleForm(request.POST)
    sample_error = []
    if form.is_valid():
        try:
            sample = sample_blueprint(
                blueprint_version=version, topic=form.cleaned_data["topic"].strip(),
                seed=form.cleaned_data["seed"], created_by=request.user,
            )
        except InsufficientQuestionPool as exc:
            sample_error = exc.shortages
        except ValidationError as exc:
            sample_error = [str(exc)]
        else:
            return redirect("blueprint_detail", blueprint_id=version.blueprint_id)
    else:
        sample_error = [str(error) for errors in form.errors.values() for error in errors]
    blueprint = blueprint_in_scope(request.user, version.blueprint_id)
    return render(request, "core/blueprint_detail.html", {
        "blueprint": blueprint,
        "is_admin": is_content_admin(request.user),
        "topic_options": list(QuestionVersion.objects.filter(
            question__course=blueprint.course, status=QuestionVersion.Status.APPROVED,
            source_reference__gt="",
        ).order_by().values_list("topic", flat=True).distinct()),
        "sample_form": form,
        "sample_error": sample_error,
    }, status=400)


def health(request):
    return JsonResponse({"status": "ok", "service": "ai-speaking-demo"})


def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready", "database": "ok"})


@role_required(ROLE_STUDENT)
def exam_start(request, version_id):
    if request.method != "POST":
        return HttpResponseForbidden("Bắt đầu kỳ thi cần POST.")
    version = get_object_or_404(
        BlueprintVersion.objects.select_related("blueprint", "blueprint__course").filter(
            pk=version_id, status=BlueprintVersion.Status.PUBLISHED,
            blueprint__course__enrollments__student=request.user,
        )
    )
    form = ExamStartForm(request.POST)
    if not form.is_valid():
        return render(request, "core/exam_start.html", {"form": form, "version": version}, status=400)
    request.session[f"official_preflight:{request.user.pk}"] = {
        "version_id": version.pk, "topic": form.cleaned_data["topic"].strip() or "official",
        "seed": form.cleaned_data["seed"], "nonce": secrets.token_urlsafe(24),
        "created_at": timezone.now().timestamp(),
    }
    return redirect("exam_preflight")


@role_required(ROLE_STUDENT)
def exam_preflight(request):
    setup = request.session.get(f"official_preflight:{request.user.pk}")
    if not setup or timezone.now().timestamp() - setup.get("created_at", 0) > 1200:
        request.session.pop(f"official_preflight:{request.user.pk}", None)
        return redirect("dashboard_student")
    version = get_object_or_404(BlueprintVersion.objects.select_related("blueprint__course"), pk=setup["version_id"], status=BlueprintVersion.Status.PUBLISHED, blueprint__course__enrollments__student=request.user)
    return render(request, "core/exam_preflight.html", {
        "setup": {"nonce": setup["nonce"], "level": version.blueprint.course.code, "question_count": sum(slot.question_count for slot in version.slots.all()), "response_seconds": max((slot.response_seconds for slot in version.slots.all()), default=0)},
        "network_probe_url": reverse("exam_network_probe"), "preflight_complete_url": reverse("exam_preflight_complete"), "practice_start_url": reverse("exam_preflight_begin"),
    })


@role_required(ROLE_STUDENT)
def exam_preflight_complete(request):
    if request.method != "POST":
        return HttpResponseForbidden("Xác nhận kiểm tra thiết bị cần POST.")
    setup = request.session.get(f"official_preflight:{request.user.pk}")
    if not setup or timezone.now().timestamp() - setup.get("created_at", 0) > 1200 or request.POST.get("nonce") != setup.get("nonce"):
        return JsonResponse({"error": "Phiên kiểm tra đã hết hạn. Hãy bắt đầu lại."}, status=400)
    try:
        speed_bps, latency_ms = int(request.POST.get("speed_bps", "0")), int(request.POST.get("latency_ms", "-1"))
    except ValueError:
        return JsonResponse({"error": "Kết quả kiểm tra không hợp lệ."}, status=400)
    if request.POST.get("mic_verified") != "1" or request.POST.get("playback_confirmed") != "1" or speed_bps < 32_768 or not 0 <= latency_ms <= 2000:
        return JsonResponse({"error": "Cần kiểm tra micro và đạt ngưỡng kết nối trước khi tiếp tục."}, status=400)
    setup.update(verified_at=timezone.now().timestamp(), speed_bps=speed_bps, latency_ms=latency_ms)
    request.session[f"official_preflight:{request.user.pk}"] = setup
    return JsonResponse({"ready": True})


@role_required(ROLE_STUDENT)
def exam_network_probe(request):
    return network_probe(request)


def _create_exam_attempt_from_preflight(request, setup):
    version = get_object_or_404(BlueprintVersion.objects.select_related("blueprint__course"), pk=setup["version_id"], status=BlueprintVersion.Status.PUBLISHED, blueprint__course__enrollments__student=request.user)
    try:
        sample = sample_blueprint(blueprint_version=version, topic=setup["topic"], seed=setup.get("seed"), created_by=request.user)
    except (InsufficientQuestionPool, ValidationError) as exc:
        raise ValidationError(getattr(exc, "shortages", str(exc)))
    questions, index = [], 1
    for section in sample.selected_snapshot:
        section_max = Decimal(str(section["slot"].get("max_points", "1")))
        count = max(len(section["questions"]), 1)
        for question in section["questions"]:
            questions.append({
                "question_index": index, "section_name": section["slot"]["section_name"],
                "task_type": section["slot"]["task_type"], "question": question,
                "rubric_snapshot": section["rubric_snapshot"], "task_max_points": str(section_max / count),
            })
            index += 1
    started_at = timezone.now()
    total_seconds = sum((slot.get("prep_seconds") or 0) + (slot.get("response_seconds") or 0) for slot in (section["slot"] for section in sample.selected_snapshot for _ in range(section["slot"]["question_count"])))
    attempt = ExamAttempt.objects.create(
        student=request.user, course=version.blueprint.course, blueprint_version=version,
        seed=sample.seed, blueprint_snapshot=sample.blueprint_snapshot, questions_snapshot=questions,
        threshold=version.pass_threshold, started_at=started_at, expires_at=started_at + timedelta(seconds=max(total_seconds, 60)),
    )
    return attempt


@role_required(ROLE_STUDENT)
def exam_preflight_begin(request):
    if request.method != "POST":
        return HttpResponseForbidden("Bắt đầu kỳ thi cần POST.")
    setup = request.session.get(f"official_preflight:{request.user.pk}")
    if not setup or not setup.get("verified_at") or timezone.now().timestamp() - setup["verified_at"] > 1200:
        return redirect("exam_preflight")
    try:
        attempt = _create_exam_attempt_from_preflight(request, setup)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("exam_start", version_id=setup["version_id"])
    request.session.pop(f"official_preflight:{request.user.pk}", None)
    return redirect("exam_detail", attempt_id=attempt.pk)


@role_required(ROLE_STUDENT)
def exam_detail(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt.objects.prefetch_related("answers"), pk=attempt_id, student=request.user)
    answers = {answer.question_index: answer for answer in attempt.answers.all()}
    items = [{"index": q["question_index"], "question": q["question"], "answer": answers.get(q["question_index"])} for q in attempt.questions_snapshot]
    return render(request, "core/exam_detail.html", {"attempt": attempt, "items": items, "saved_count": len(answers)})


@role_required(ROLE_STUDENT)
def exam_answer_upload(request, attempt_id):
    if request.method != "POST":
        return HttpResponseForbidden("Lưu câu trả lời cần POST.")
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return HttpResponseForbidden("Bài thi đã nộp.")
    if attempt.expires_at and timezone.now() > attempt.expires_at:
        attempt.status = ExamAttempt.Status.SUBMITTED
        attempt.scoring_status = ExamAttempt.ScoringStatus.NEEDS_REVIEW
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=("status", "scoring_status", "submitted_at"))
        messages.error(request, "Thời gian bài thi đã hết; bài đã được khóa.")
        return redirect("exam_detail", attempt_id=attempt.pk)
    form = PracticeAnswerForm(request.POST, request.FILES)
    if form.is_valid():
        index = form.cleaned_data["question_index"]
        question = next((item for item in attempt.questions_snapshot if item["question_index"] == index), None)
        if not question or form.cleaned_data["duration_seconds"] > int(question["question"].get("response_seconds") or 1):
            return HttpResponseForbidden("Câu hỏi hoặc thời lượng ghi âm không hợp lệ.")
        if not attempt.answers.filter(question_index=index).exists():
            ExamAnswer.objects.create(
                attempt=attempt, question_index=index, audio=form.cleaned_data["audio"],
                audio_extension=form.cleaned_data["audio_extension"], content_type=form.cleaned_data["audio_mime"],
                duration_seconds=form.cleaned_data["duration_seconds"],
            )
            messages.success(request, f"Đã lưu bản ghi câu {index}.")
    else:
        messages.error(request, "Không lưu được bản ghi: " + "; ".join(error for errors in form.errors.values() for error in errors))
    return redirect("exam_detail", attempt_id=attempt.pk)


@role_required(ROLE_STUDENT)
def exam_submit(request, attempt_id):
    if request.method != "POST":
        return HttpResponseForbidden("Nộp bài cần POST.")
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return HttpResponseForbidden("Bài thi đã nộp.")
    if attempt.expires_at and timezone.now() > attempt.expires_at:
        attempt.status = ExamAttempt.Status.SUBMITTED
        attempt.scoring_status = ExamAttempt.ScoringStatus.NEEDS_REVIEW
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=("status", "scoring_status", "submitted_at"))
        messages.error(request, "Thời gian bài thi đã hết; bài đã được khóa.")
        return redirect("exam_detail", attempt_id=attempt.pk)
    if attempt.answers.count() != len(attempt.questions_snapshot):
        messages.error(request, "Hãy lưu bản ghi cho tất cả câu hỏi trước khi nộp bài.")
        return redirect("exam_detail", attempt_id=attempt.pk)
    attempt.status = ExamAttempt.Status.SUBMITTED
    attempt.scoring_status = ExamAttempt.ScoringStatus.NEEDS_REVIEW
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=("status", "scoring_status", "submitted_at"))
    messages.success(request, "Đã khóa bài thi. Bài đang chờ chấm và rà soát.")
    return redirect("exam_detail", attempt_id=attempt.pk)


@login_required
def exam_answer_audio(request, answer_id):
    answer = get_object_or_404(ExamAnswer.objects.select_related("attempt"), pk=answer_id)
    allowed = answer.attempt.student_id == request.user.pk or is_content_admin(request.user) or CourseTeachingAssignment.objects.filter(
        course=answer.attempt.course, teacher=request.user, is_active=True,
    ).exists()
    if not allowed:
        return HttpResponseForbidden("Không có quyền nghe bản ghi thi.")
    return FileResponse(answer.audio.open("rb"), content_type=answer.content_type)


@login_required
def exam_review_queue(request):
    if not (is_content_admin(request.user) or request.user.groups.filter(name=ROLE_TEACHER).exists()):
        return HttpResponseForbidden("Chức năng này dành cho giảng viên và quản trị viên.")
    attempts = ExamAttempt.objects.filter(
        status=ExamAttempt.Status.SUBMITTED,
    ).exclude(scoring_status=ExamAttempt.ScoringStatus.FINAL).select_related(
        "course", "student", "blueprint_version", "reviewed_by",
    ).order_by("submitted_at", "id")
    if not is_content_admin(request.user):
        attempts = attempts.filter(course__teaching_assignments__teacher=request.user, course__teaching_assignments__is_active=True)
    return render(request, "core/exam_review_queue.html", {"attempts": attempts, "claim_form": ExamClaimForm()})


@login_required
def exam_review_claim(request, attempt_id):
    if request.method != "POST":
        return HttpResponseForbidden("Claim attempt cần POST.")
    if not (is_content_admin(request.user) or request.user.groups.filter(name=ROLE_TEACHER).exists()):
        return HttpResponseForbidden("Chức năng này dành cho giảng viên và quản trị viên.")
    queryset = ExamAttempt.objects.select_for_update()
    if not is_content_admin(request.user):
        queryset = queryset.filter(course__teaching_assignments__teacher=request.user, course__teaching_assignments__is_active=True)
    with transaction.atomic():
        attempt = get_object_or_404(queryset, pk=attempt_id, status=ExamAttempt.Status.SUBMITTED)
        if attempt.reviewed_by_id and attempt.reviewed_by_id != request.user.pk:
            messages.error(request, "Attempt này đã được giảng viên khác nhận chấm.")
        else:
            attempt.reviewed_by = request.user
            attempt.save(update_fields=("reviewed_by",))
            messages.success(request, "Đã nhận attempt để chấm.")
    return redirect("exam_review_queue")


@login_required
def exam_review(request, attempt_id):
    if not (is_content_admin(request.user) or request.user.groups.filter(name=ROLE_TEACHER).exists()):
        return HttpResponseForbidden("Chức năng này dành cho giảng viên và quản trị viên.")
    attempts = ExamAttempt.objects.select_related("course", "student").prefetch_related("answers")
    if not is_content_admin(request.user):
        attempts = attempts.filter(course__teaching_assignments__teacher=request.user, course__teaching_assignments__is_active=True)
    attempt = get_object_or_404(attempts, pk=attempt_id)
    form = ExamScoreForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                result = score_official_attempt(attempt=attempt, answers_payload=form.cleaned_data["score_payload"], actor=request.user, reason=form.cleaned_data["reason"])
                ExamScoreDecision.objects.create(
                    attempt=attempt, actor=request.user, decision=result["status"], score=attempt.final_score,
                    payload=result, reason=form.cleaned_data["reason"].strip(),
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("exam_review", attempt_id=attempt.pk)
    return render(request, "core/exam_review.html", {"attempt": attempt, "form": form})
