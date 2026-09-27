from decimal import Decimal, InvalidOperation
import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from core.models import Course, QuestionTag, QuestionVersion
from core.models import (
    CEFR_LEVELS, CEFR_ORDER, RUBRIC_BANDS, RUBRIC_SIGNAL_VALUES,
    BlueprintVersion, RubricVersion,
)


COURSE_LEVELS = {"1": ("A1", "A2"), "2": ("A2", "B1"), "3": ("B1", "B2"), "4": ("B2", "C1")}
DEMO_ACCOUNT_ROLES = (
    ("student", "Sinh viên"),
    ("teacher", "Giảng viên"),
    ("admin", "Quản trị viên"),
)


class DemoAccountForm(forms.Form):
    username = forms.RegexField(
        regex=r"^demo-[\w.@+-]+$", max_length=150, label="Tên đăng nhập",
        error_messages={"invalid": "Tên đăng nhập phải bắt đầu bằng demo-."},
    )
    email = forms.EmailField(label="Email")
    role = forms.ChoiceField(choices=DEMO_ACCOUNT_ROLES, label="Vai trò")
    is_active = forms.BooleanField(required=False, initial=True, label="Tài khoản đang hoạt động")
    password = forms.CharField(
        required=False, label="Mật khẩu", widget=forms.PasswordInput(render_value=False),
        help_text="Bắt buộc khi tạo; để trống khi sửa để giữ mật khẩu hiện tại.",
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if instance:
            self.initial.update({
                "username": instance.username,
                "email": instance.email,
                "is_active": instance.is_active,
            })
            self.initial["role"] = instance.groups.filter(name__in=[r[0] for r in DEMO_ACCOUNT_ROLES]).values_list("name", flat=True).first() or "student"
        if instance:
            self.fields["username"].disabled = True

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        users = get_user_model().objects.filter(username__iexact=username)
        if self.instance:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError("Tên đăng nhập này đã được sử dụng.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if not self.instance and not password:
            self.add_error("password", "Hãy nhập mật khẩu cho tài khoản mới.")
        elif password:
            user = get_user_model()(username=cleaned.get("username", ""), email=cleaned.get("email", ""))
            try:
                validate_password(password, user=user)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class PracticeCreateForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.none(), label="Học phần")
    level = forms.ChoiceField(choices=CEFR_LEVELS, label="Trình độ CEFR")
    topic = forms.CharField(max_length=120, required=False, label="Chủ đề (để trống để AI chọn)")
    question_count = forms.IntegerField(min_value=1, max_value=8, initial=3, label="Số câu hỏi")
    response_seconds = forms.IntegerField(min_value=15, max_value=240, initial=60, label="Thời gian mỗi câu (giây)")

    def __init__(self, *args, courses, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = courses
        selected = None
        if self.is_bound:
            try:
                selected = courses.get(pk=self.data.get("course"))
            except (Course.DoesNotExist, TypeError, ValueError):
                pass
        if selected is None:
            selected = courses.first()
        if selected and not self.is_bound:
            self.fields["course"].initial = selected.pk
        if selected:
            match = re.search(r"(?:GT|GIAO\s*TIẾP\s*)?([1-4])\b", f"{selected.code} {selected.name}", re.I)
            levels = COURSE_LEVELS.get(match.group(1)) if match else None
            if levels:
                self.fields["level"].choices = [(level, level) for level in levels]

    def clean_topic(self):
        return self.cleaned_data["topic"].strip()


class PracticeAnswerForm(forms.Form):
    question_index = forms.IntegerField(min_value=1)
    duration_seconds = forms.IntegerField(min_value=1, max_value=240)
    audio = forms.FileField()

    def clean_audio(self):
        audio = self.cleaned_data["audio"]
        if audio.size > 25 * 1024 * 1024:
            raise forms.ValidationError("Bản ghi tối đa 25 MB.")
        mime = (audio.content_type or "").split(";", 1)[0].lower()
        signatures = {
            "audio/webm": lambda data: data.startswith(b"\x1a\x45\xdf\xa3"),
            "video/webm": lambda data: data.startswith(b"\x1a\x45\xdf\xa3"),
            "audio/ogg": lambda data: data.startswith(b"OggS"),
            "audio/wav": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WAVE",
            "audio/x-wav": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WAVE",
            "audio/mp4": lambda data: data[4:8] == b"ftyp",
            "audio/mpeg": lambda data: data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0),
        }
        check = signatures.get(mime)
        head = audio.read(16)
        audio.seek(0)
        if not check or not check(head):
            raise forms.ValidationError("Chỉ chấp nhận bản ghi âm thanh WebM, Ogg, WAV, MP4/M4A hoặc MP3 hợp lệ.")
        self.cleaned_data["audio_mime"] = "audio/webm" if mime == "video/webm" else mime
        self.cleaned_data["audio_extension"] = {
            "audio/webm": "webm", "video/webm": "webm", "audio/ogg": "ogg",
            "audio/wav": "wav", "audio/x-wav": "wav", "audio/mp4": "m4a", "audio/mpeg": "mp3",
        }[mime]
        return audio


class PracticeReviewForm(forms.Form):
    score = forms.DecimalField(min_value=0, max_value=100, max_digits=5, decimal_places=2, label="Điểm cuối (0–100)")
    feedback = forms.CharField(max_length=4000, required=False, label="Nhận xét của giảng viên", widget=forms.Textarea)


class ExamStartForm(forms.Form):
    topic = forms.CharField(max_length=160, required=False, label="Nhóm chủ đề")
    seed = forms.IntegerField(required=False, min_value=0, max_value=(2**63) - 1)


class ExamScoreForm(forms.Form):
    score_payload = forms.JSONField(widget=forms.Textarea(attrs={"rows": 18, "spellcheck": "false"}))
    reason = forms.CharField(max_length=2000, label="Lý do quyết định")


class QuestionImportForm(forms.Form):
    payload = forms.JSONField(
        widget=forms.Textarea(attrs={"rows": 24, "spellcheck": "false"}),
        label="Danh sách câu hỏi JSON",
        help_text="Mỗi phần tử cần language, task_type, topic, prompt_text, target_level_min/max, prep_seconds, response_seconds, source_reference và exam_metadata.",
    )


class ExamClaimForm(forms.Form):
    attempt_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class QuestionVersionForm(forms.ModelForm):
    class Meta:
        model = QuestionVersion
        fields = (
            "language", "task_type", "topic", "target_level_min", "target_level_max",
            "prompt_text", "candidate_instructions", "prep_seconds", "response_seconds",
            "required_points", "optional_prompts", "allowed_alternatives", "criterion_refs",
            "source_reference", "source_notes", "exam_metadata", "tags",
        )
        widgets = {
            "prompt_text": forms.Textarea(attrs={"rows": 4}),
            "candidate_instructions": forms.Textarea(attrs={"rows": 3}),
            "required_points": forms.Textarea(attrs={"rows": 3}),
            "optional_prompts": forms.Textarea(attrs={"rows": 3}),
            "allowed_alternatives": forms.Textarea(attrs={"rows": 3}),
            "criterion_refs": forms.Textarea(attrs={"rows": 3}),
            "source_notes": forms.Textarea(attrs={"rows": 3}),
            "exam_metadata": forms.Textarea(attrs={"rows": 6, "spellcheck": "false"}),
        }
        help_texts = {
            "required_points": "Nhập danh sách JSON; chỉ dùng nội dung đã đối chiếu tài liệu môn.",
            "optional_prompts": "Danh sách JSON, có thể để trống.",
            "allowed_alternatives": "Danh sách JSON, có thể để trống.",
            "criterion_refs": "Danh sách mã tiêu chí rubric đã được duyệt; không tự tạo rubric.",
            "source_reference": "Tên/mã tài liệu và vị trí nguồn để truy nguyên.",
            "exam_metadata": "Object JSON dùng để sampler lọc content_family, phoneme_targets, sentence_type, syllable_group và độ dài.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].queryset = QuestionTag.objects.order_by("name")
        self.fields["tags"].required = False


class RubricVersionForm(forms.ModelForm):
    criteria_payload = forms.JSONField(
        label="Tiêu chí và descriptor theo cấp độ",
        widget=forms.Textarea(attrs={"rows": 18, "spellcheck": "false"}),
        help_text=(
            'JSON dạng [{"name":"...","description":"...","weight":20,'
            '"signal":"audio","descriptors":[{"level":"0","text":"..."}, ...]}]. '
            "Descriptor phải đủ band 0–4; tổng weight phải bằng 100."
        ),
    )

    class Meta:
        model = RubricVersion
        fields = (
            "title", "section_name", "task_type", "target_level_min", "target_level_max",
            "source_reference", "source_notes",
        )
        widgets = {"source_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["criteria_payload"] = self.instance.content_snapshot()["criteria"]

    def clean_criteria_payload(self):
        criteria = self.cleaned_data["criteria_payload"]
        valid_levels = {level for level, _ in RUBRIC_BANDS}
        if not isinstance(criteria, list) or not criteria:
            raise forms.ValidationError("Thêm ít nhất một tiêu chí dạng danh sách JSON.")
        names = set()
        for index, item in enumerate(criteria, start=1):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
                raise forms.ValidationError(f"Tiêu chí {index}: cần có name dạng văn bản.")
            name = item["name"].strip()
            if name.casefold() in names:
                raise forms.ValidationError(f"Tên tiêu chí bị lặp: {name}.")
            names.add(name.casefold())
            if set(item) - {"name", "description", "weight", "signal", "bands", "max_points", "descriptors"}:
                raise forms.ValidationError(f"Tiêu chí {index}: có thuộc tính không được hỗ trợ.")
            if not isinstance(item.get("description", ""), str):
                raise forms.ValidationError(f"Tiêu chí {index}: description phải là văn bản.")
            weight = item.get("weight")
            try:
                parsed_weight = Decimal(str(weight))
            except (InvalidOperation, ValueError):
                raise forms.ValidationError(f"Tiêu chí {index}: weight phải là số trong khoảng 0–100.")
            if not parsed_weight.is_finite() or parsed_weight <= 0 or parsed_weight > 100:
                raise forms.ValidationError(f"Tiêu chí {index}: weight phải là số trong khoảng 0–100.")
            if item.get("signal") not in RUBRIC_SIGNAL_VALUES:
                raise forms.ValidationError(f"Tiêu chí {index}: signal không hợp lệ.")
            points = item.get("max_points")
            if points is not None:
                try:
                    parsed_points = Decimal(str(points))
                except (InvalidOperation, ValueError):
                    raise forms.ValidationError(f"Tiêu chí {index}: max_points phải là số dương hoặc null.")
                if not parsed_points.is_finite() or parsed_points <= 0:
                    raise forms.ValidationError(f"Tiêu chí {index}: max_points phải là số dương hoặc null.")
            descriptors = item.get("descriptors")
            if not isinstance(descriptors, list) or not descriptors:
                raise forms.ValidationError(f"Tiêu chí {index}: cần ít nhất một descriptor theo level.")
            used_levels = set()
            for descriptor in descriptors:
                if not isinstance(descriptor, dict) or set(descriptor) != {"level", "text"}:
                    raise forms.ValidationError(f"Tiêu chí {index}: descriptor cần có level và text.")
                level, text = descriptor["level"], descriptor["text"]
                if not isinstance(level, str) or level not in valid_levels or not isinstance(text, str) or not text.strip():
                    raise forms.ValidationError(f"Tiêu chí {index}: level hoặc descriptor không hợp lệ.")
                if level in used_levels:
                    raise forms.ValidationError(f"Tiêu chí {index}: level {level} bị lặp.")
                used_levels.add(level)
        total_weight = sum((Decimal(str(item["weight"])) for item in criteria), Decimal("0"))
        if total_weight != Decimal("100"):
            raise forms.ValidationError("Tổng weight của các tiêu chí phải bằng 100.")
        return criteria


class BlueprintVersionForm(forms.ModelForm):
    slots_payload = forms.JSONField(
        label="Các phần/slot của đề",
        widget=forms.Textarea(attrs={"rows": 20, "spellcheck": "false"}),
        help_text=(
            'JSON list với section_name, task_type, question_count, target_level_min/max, '
            'language, prep_seconds, response_seconds, selection_rules (object), rubric_version_id.'
        ),
    )

    class Meta:
        model = BlueprintVersion
        fields = ("title", "source_reference", "source_notes", "assessment_type", "pass_threshold")
        widgets = {"source_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, rubric_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rubric_queryset = rubric_queryset if rubric_queryset is not None else RubricVersion.objects.none()
        if self.instance.pk:
            self.initial["slots_payload"] = [
                {
                    "section_name": slot["section_name"],
                    "task_type": slot["task_type"],
                    "question_count": slot["question_count"],
                    "target_level_min": slot["target_level_min"],
                    "target_level_max": slot["target_level_max"],
                    "language": slot["language"],
                    "prep_seconds": slot["prep_seconds"],
                    "response_seconds": slot["response_seconds"],
                    "selection_rules": slot["selection_rules"],
                    "max_points": slot["max_points"],
                    "rubric_version_id": slot["rubric_version_id"],
                }
                for slot in self.instance.content_snapshot()["slots"]
            ]

    def clean_slots_payload(self):
        slots = self.cleaned_data["slots_payload"]
        levels = {level for level, _ in CEFR_LEVELS}
        required = {
            "section_name", "task_type", "question_count", "target_level_min", "target_level_max",
            "language", "prep_seconds", "response_seconds", "rubric_version_id",
        }
        allowed = required | {"selection_rules", "max_points"}
        if not isinstance(slots, list) or not slots:
            raise forms.ValidationError("Blueprint cần ít nhất một slot dạng JSON list.")
        sections = set()
        for index, slot in enumerate(slots, start=1):
            if not isinstance(slot, dict) or not required.issubset(slot) or set(slot) - allowed:
                raise forms.ValidationError(f"Slot {index}: các trường JSON chưa đúng cấu trúc.")
            for key, max_length in (("section_name", 120), ("task_type", 64), ("language", 16)):
                value = slot[key]
                if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
                    raise forms.ValidationError(f"Slot {index}: {key} cần có nội dung hợp lệ.")
                slot[key] = value.strip()
            section_key = slot["section_name"].casefold()
            if section_key in sections:
                raise forms.ValidationError(f"Tên section bị lặp: {slot['section_name']}.")
            sections.add(section_key)
            low, high = slot["target_level_min"], slot["target_level_max"]
            if not isinstance(low, str) or not isinstance(high, str) or low not in levels or high not in levels:
                raise forms.ValidationError(f"Slot {index}: dải CEFR không hợp lệ.")
            if CEFR_ORDER[low] > CEFR_ORDER[high]:
                raise forms.ValidationError(f"Slot {index}: mức tối đa phải bằng hoặc cao hơn mức tối thiểu.")
            count = slot["question_count"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise forms.ValidationError(f"Slot {index}: question_count phải là số nguyên dương.")
            response_seconds = slot["response_seconds"]
            if isinstance(response_seconds, bool) or not isinstance(response_seconds, int) or response_seconds < 1:
                raise forms.ValidationError(f"Slot {index}: response_seconds phải là số nguyên dương.")
            prep_seconds = slot["prep_seconds"]
            if prep_seconds is not None and (
                isinstance(prep_seconds, bool) or not isinstance(prep_seconds, int) or prep_seconds < 0
            ):
                raise forms.ValidationError(f"Slot {index}: prep_seconds phải là số nguyên không âm hoặc null.")
            slot["selection_rules"] = slot.get("selection_rules") or {}
            if not isinstance(slot["selection_rules"], dict):
                raise forms.ValidationError(f"Slot {index}: selection_rules phải là object JSON.")
            try:
                slot["max_points"] = str(Decimal(str(slot.get("max_points", "1"))))
                if Decimal(slot["max_points"]) <= 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                raise forms.ValidationError(f"Slot {index}: max_points phải là số dương.")
            rubric_id = slot["rubric_version_id"]
            if isinstance(rubric_id, bool) or not isinstance(rubric_id, int) or rubric_id < 1:
                raise forms.ValidationError(f"Slot {index}: rubric_version_id không hợp lệ.")
            rubric = self.rubric_queryset.filter(pk=rubric_id).select_related("rubric").first()
            if not rubric:
                raise forms.ValidationError(f"Slot {index}: hãy chọn rubric đã xuất bản của học phần này.")
            if rubric.section_name != slot["section_name"] or rubric.task_type != slot["task_type"]:
                raise forms.ValidationError(f"Slot {index}: section/task không khớp rubric đã chọn.")
            if rubric.target_level_min and CEFR_ORDER[rubric.target_level_min] > CEFR_ORDER[low]:
                raise forms.ValidationError(f"Slot {index}: rubric không bao phủ mức {low}.")
            if rubric.target_level_max and CEFR_ORDER[rubric.target_level_max] < CEFR_ORDER[high]:
                raise forms.ValidationError(f"Slot {index}: rubric không bao phủ mức {high}.")
            required_levels = {
                level for level, _ in CEFR_LEVELS
                if CEFR_ORDER[low] <= CEFR_ORDER[level] <= CEFR_ORDER[high]
            }
            for criterion in rubric.criteria.prefetch_related("descriptors"):
                descriptor_levels = {item.level for item in criterion.descriptors.all()}
                if not required_levels.issubset(descriptor_levels):
                    raise forms.ValidationError(f"Slot {index}: rubric thiếu descriptor cho dải CEFR.")
        return slots


class BlueprintSampleForm(forms.Form):
    topic = forms.CharField(max_length=160)
    seed = forms.IntegerField(required=False, min_value=0, max_value=(2**63) - 1)
