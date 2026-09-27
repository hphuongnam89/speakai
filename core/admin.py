from django.contrib import admin

from core.models import Course, CourseTeachingAssignment, QuestionTag


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(CourseTeachingAssignment)
class CourseTeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ("teacher", "course", "is_active", "assigned_at")
    list_filter = ("is_active", "course")
    search_fields = ("teacher__username", "course__code", "course__name")


@admin.register(QuestionTag)
class QuestionTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
