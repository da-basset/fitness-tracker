from django.contrib import admin

from .models import (
    CompletedSet,
    Exercise,
    Phase,
    Plan,
    PlanAssignment,
    Week,
    WeekDay,
    Workout,
    WorkoutCompletion,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "trainer", "created_at")


@admin.register(PlanAssignment)
class PlanAssignmentAdmin(admin.ModelAdmin):
    list_display = ("plan", "client", "is_active", "assigned_at")
    list_filter = ("is_active",)


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("name", "plan", "sub", "color", "order")
    list_filter = ("plan",)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("workout", "segment", "name", "sets_count", "rest_seconds", "is_custom", "created_by")
    list_filter = ("workout", "segment", "is_custom")


class WeekDayInline(admin.TabularInline):
    model = WeekDay
    extra = 0


class WeekInline(admin.TabularInline):
    model = Week
    extra = 0


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("title", "plan", "duration_weeks", "order")
    list_filter = ("plan",)
    inlines = [WeekInline]


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ("phase", "label", "order")
    inlines = [WeekDayInline]


@admin.register(CompletedSet)
class CompletedSetAdmin(admin.ModelAdmin):
    list_display = ("client", "exercise", "log_date", "set_number", "completed_at")
    list_filter = ("log_date", "client")


@admin.register(WorkoutCompletion)
class WorkoutCompletionAdmin(admin.ModelAdmin):
    list_display = ("client", "workout", "week", "log_date", "completed_at")
    list_filter = ("log_date", "client", "week")
