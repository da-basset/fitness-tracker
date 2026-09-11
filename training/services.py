"""Plan-cloning logic shared by the "assign a plan" view and (in inlined
form, since data migrations can't import app code) migration 0014."""

from .models import Exercise, Nutrient, Phase, Plan, Supplement, Week, WeekDay, Workout


def clone_plan_for_client(template_plan, client):
    """Deep-copies template_plan's full Phase/Week/WeekDay + Workout/
    Exercise tree, plus its Nutrients and Supplements lists, into a
    brand-new Plan tied to `client`. The clone is
    completely independent of the template and of any other client's
    copy -- editing it later never touches the template or any other
    client's plan. Does not create the PlanAssignment itself; the caller
    is responsible for that (and for deactivating any previous active
    assignment first)."""
    new_plan = Plan.objects.create(
        trainer=template_plan.trainer,
        name=template_plan.name,
        description=template_plan.description,
        source_plan=template_plan,
    )

    workout_map = {}
    for w in template_plan.workouts.all():
        new_w = Workout.objects.create(
            plan=new_plan, name=w.name, sub=w.sub, flavor=w.flavor,
            color=w.color, order=w.order,
        )
        workout_map[w.id] = new_w
        for ex in w.exercises.all():
            Exercise.objects.create(
                workout=new_w, segment=ex.segment, name=ex.name,
                sets_count=ex.sets_count, reps_text=ex.reps_text,
                rest_seconds=ex.rest_seconds, time_text=ex.time_text,
                order=ex.order, is_custom=ex.is_custom, created_by=ex.created_by,
            )

    for nutrient in template_plan.nutrients.all():
        Nutrient.objects.create(
            plan=new_plan, name=nutrient.name, amount=nutrient.amount,
            timing=nutrient.timing, notes=nutrient.notes, order=nutrient.order,
        )

    for supplement in template_plan.supplements.all():
        Supplement.objects.create(
            plan=new_plan, name=supplement.name, amount=supplement.amount,
            timing=supplement.timing, notes=supplement.notes, order=supplement.order,
        )

    for phase in template_plan.phases.prefetch_related("weeks__days"):
        new_phase = Phase.objects.create(
            plan=new_plan, title=phase.title, note=phase.note, order=phase.order,
        )
        for week in phase.weeks.all():
            new_week = Week.objects.create(phase=new_phase, order=week.order)
            for day in week.days.all():
                new_workout = workout_map.get(day.workout_id) if day.workout_id else None
                WeekDay.objects.create(week=new_week, weekday=day.weekday, workout=new_workout)

    return new_plan
