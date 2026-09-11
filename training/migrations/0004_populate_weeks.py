# Hand-written data migration: expands each existing Phase's single
# repeating (duration_weeks x weekday->workout) schedule into that many
# individual Week rows, each with its own copy of the same day-by-day
# WeekDay schedule -- a faithful snapshot of "what this phase looked like
# before weeks became independently editable." Also repoints existing
# WorkoutCompletion rows from the phase they were logged under to that
# phase's first week (order=1), since a completion only ever recorded
# which phase tab was open, not which specific week -- there's no way to
# recover that after the fact, so the first week is the closest
# approximation for the (typically very few) rows this affects.
from django.db import migrations


def populate_weeks(apps, schema_editor):
    Phase = apps.get_model("training", "Phase")
    Week = apps.get_model("training", "Week")
    WeekDay = apps.get_model("training", "WeekDay")
    WorkoutCompletion = apps.get_model("training", "WorkoutCompletion")

    first_week_by_phase = {}

    for phase in Phase.objects.all():
        old_days = list(phase.days.all())  # existing PhaseDay rows
        first_week = None
        for week_order in range(1, phase.duration_weeks + 1):
            week = Week.objects.create(phase=phase, order=week_order)
            if first_week is None:
                first_week = week
            for old_day in old_days:
                WeekDay.objects.create(
                    week=week, weekday=old_day.weekday, workout_id=old_day.workout_id
                )
        if first_week is not None:
            first_week_by_phase[phase.id] = first_week.id

    for completion in WorkoutCompletion.objects.exclude(phase=None):
        week_id = first_week_by_phase.get(completion.phase_id)
        if week_id:
            completion.week_id = week_id
            completion.save(update_fields=["week"])


def reverse_noop(apps, schema_editor):
    # Reversing would mean deleting every Week/WeekDay -- destructive and
    # not needed (0005 drops the old fields this depends on anyway), so
    # this migration is one-way.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0003_week_workoutcompletion_week_weekday"),
    ]

    operations = [
        migrations.RunPython(populate_weeks, reverse_noop),
    ]
