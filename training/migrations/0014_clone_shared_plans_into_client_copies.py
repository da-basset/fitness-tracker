from django.db import migrations


def clone_shared_plans_into_client_copies(apps, schema_editor):
    """Retrofits the old "one shared Plan" model into the new "each
    assignment is an independent copy" model. Before this migration, every
    Plan that had ever been assigned to a client was literally the same
    row every assigned client (and, via the client-editable exercise API
    that's being locked down in this same release, every one of those
    clients) read and wrote against. For each such Plan, and for each
    distinct client it's (or was) assigned to, this deep-clones the plan's
    full Phase/Week/WeekDay + Workout/Exercise tree into a brand-new Plan,
    repoints that one PlanAssignment at the clone, and repoints that
    client's own CompletedSet/WorkoutCompletion rows from the old
    workout/exercise ids to the new cloned ones so their logged history
    keeps rendering correctly. Once every assignment on a plan has been
    repointed this way, the original Plan is left with zero assignments --
    which is exactly the definition of a reusable library template, so no
    separate flag is needed to mark it as one.
    """
    Plan = apps.get_model("training", "Plan")
    PlanAssignment = apps.get_model("training", "PlanAssignment")
    Workout = apps.get_model("training", "Workout")
    Exercise = apps.get_model("training", "Exercise")
    Phase = apps.get_model("training", "Phase")
    Week = apps.get_model("training", "Week")
    WeekDay = apps.get_model("training", "WeekDay")
    CompletedSet = apps.get_model("training", "CompletedSet")
    WorkoutCompletion = apps.get_model("training", "WorkoutCompletion")

    # Snapshot first -- clones created below must never be reprocessed.
    original_plan_ids = list(Plan.objects.values_list("id", flat=True))

    for plan_id in original_plan_ids:
        plan = Plan.objects.get(pk=plan_id)
        assignments = list(PlanAssignment.objects.filter(plan=plan))
        if not assignments:
            continue  # already a template (or a fresh plan with nothing assigned yet)

        workouts = list(Workout.objects.filter(plan=plan))
        exercises_by_workout = {
            w.id: list(Exercise.objects.filter(workout_id=w.id)) for w in workouts
        }
        phases = list(Phase.objects.filter(plan=plan))
        weeks_by_phase = {p.id: list(Week.objects.filter(phase_id=p.id)) for p in phases}
        days_by_week = {}
        for weeks in weeks_by_phase.values():
            for week in weeks:
                days_by_week[week.id] = list(WeekDay.objects.filter(week_id=week.id))

        for assignment in assignments:
            client = assignment.client

            new_plan = Plan.objects.create(
                trainer_id=plan.trainer_id,
                name=plan.name,
                description=plan.description,
                source_plan_id=plan.id,
            )

            workout_map = {}
            exercise_map = {}
            for w in workouts:
                new_w = Workout.objects.create(
                    plan=new_plan, name=w.name, sub=w.sub, flavor=w.flavor,
                    color=w.color, order=w.order,
                )
                workout_map[w.id] = new_w.id
                for ex in exercises_by_workout.get(w.id, []):
                    new_ex = Exercise.objects.create(
                        workout_id=new_w.id, segment=ex.segment, name=ex.name,
                        sets_count=ex.sets_count, reps_text=ex.reps_text,
                        rest_seconds=ex.rest_seconds, time_text=ex.time_text,
                        order=ex.order, is_custom=ex.is_custom,
                        created_by_id=ex.created_by_id,
                    )
                    exercise_map[ex.id] = new_ex.id

            for phase in phases:
                new_phase = Phase.objects.create(
                    plan=new_plan, title=phase.title, note=phase.note, order=phase.order,
                )
                for week in weeks_by_phase.get(phase.id, []):
                    new_week = Week.objects.create(phase=new_phase, order=week.order)
                    for day in days_by_week.get(week.id, []):
                        new_workout_id = workout_map.get(day.workout_id) if day.workout_id else None
                        WeekDay.objects.create(
                            week=new_week, weekday=day.weekday, workout_id=new_workout_id,
                        )

            assignment.plan = new_plan
            assignment.save(update_fields=["plan"])

            for cs in CompletedSet.objects.filter(client=client, exercise_id__in=exercise_map.keys()):
                cs.exercise_id = exercise_map[cs.exercise_id]
                cs.save(update_fields=["exercise_id"])
            for wc in WorkoutCompletion.objects.filter(client=client, workout_id__in=workout_map.keys()):
                wc.workout_id = workout_map[wc.workout_id]
                wc.save(update_fields=["workout_id"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0013_plan_source_plan"),
    ]

    operations = [
        migrations.RunPython(clone_shared_plans_into_client_copies, noop_reverse),
    ]
