import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.models import Client, Trainer
from accounts.permissions import can_manage_trainer

from .forms import NutrientForm, PhaseForm, PlanForm, SupplementForm, WorkoutForm
from .models import (
    MAX_PHASES,
    MAX_WEEKS_PER_PHASE,
    CompletedSet,
    Exercise,
    Nutrient,
    Phase,
    Plan,
    PlanAssignment,
    Supplement,
    Week,
    WeekDay,
    Workout,
    WorkoutCompletion,
)
from .services import clone_plan_for_client


def _get_client_active_plan(request):
    """Resolve the requesting user's Client profile and their currently
    active assigned Plan. This is the boundary that keeps one client from
    ever seeing or touching another client's (or another trainer's) data --
    every client-facing view scopes its queries through the returned plan."""
    client = get_object_or_404(Client, user=request.user)
    assignment = (
        PlanAssignment.objects.filter(client=client, is_active=True).select_related("plan").first()
    )
    if assignment is None:
        raise Http404("No plan is currently assigned to you.")
    return client, assignment.plan


# --- Permission boundaries for trainer/owner plan management ---
#
# Only a Trainer themselves, or the Owner of the Gym that Trainer belongs
# to, may ever create/edit/delete a Plan's Workouts, Phases, Weeks, or
# Exercises -- this is the single choke point for that rule. A client may
# *view* (never edit) a plan currently or previously assigned to them, so
# they can browse their own history.

def _can_manage_plan(user, plan):
    return can_manage_trainer(user, plan.trainer)


def _can_view_plan(user, plan):
    if _can_manage_plan(user, plan):
        return True
    return plan.assignments.filter(client__user=user).exists()


def _require_manage(request, plan):
    if not _can_manage_plan(request.user, plan):
        raise Http404("You don't have access to this plan.")


def _require_view(request, plan):
    if not _can_view_plan(request.user, plan):
        raise Http404("You don't have access to this plan.")


def _require_manage_trainer(request, trainer):
    if not can_manage_trainer(request.user, trainer):
        raise Http404("You don't have access to this trainer.")


def _plan_owning_client(plan):
    """The one Client this specific Plan row belongs to, if any -- a
    template (never assigned) has none; a client's copy is created once,
    at assign-time, for exactly one client, and keeps that owner even
    after being unassigned (is_active=False) so history keeps working."""
    assignment = plan.assignments.select_related("client").first()
    return assignment.client if assignment else None


@login_required
def hub(request):
    return render(request, "training/hub.html", {"training_current": True})


@login_required
def physical(request):
    return render(request, "training/physical.html")


@login_required
def spanish(request):
    return render(request, "training/spanish.html")


@login_required
def reading(request):
    return render(request, "training/reading.html")


# --- Client's own JSON API (live schedule + today's tracking) ---

@login_required
@require_http_methods(["GET"])
def api_schedule(request):
    """Workouts and the phase/week/day schedule for the requesting client's
    currently assigned plan -- driven by whatever's currently configured in
    the Phase & Week editor for that plan, not hardcoded here."""
    client, plan = _get_client_active_plan(request)
    return JsonResponse(_schedule_payload(plan, client))


@login_required
@require_http_methods(["GET"])
def api_workout(request, workout_id):
    client, plan = _get_client_active_plan(request)
    workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
    return JsonResponse(_workout_payload(workout, client))


@login_required
@require_http_methods(["POST"])
def api_toggle_set(request, exercise_id, set_number):
    client, plan = _get_client_active_plan(request)
    exercise = get_object_or_404(Exercise, pk=exercise_id, workout__plan=plan)
    return JsonResponse(_toggle_set(client, exercise, set_number))


@login_required
@require_http_methods(["POST"])
def api_toggle_workout_complete(request, workout_id):
    """Toggle today's "Mark Completed" flag for this specific workout. Each
    workout tracks its own completed state for today independently (see
    WorkoutCompletion's docstring) -- marking a different workout complete
    elsewhere doesn't affect this one. The optional week_id in the payload
    records which week tab was open, so the returned week_tally (and this
    client's future consistency history) stays attributed to the right
    week."""
    client, plan = _get_client_active_plan(request)
    workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    week_id = payload.get("week_id")
    week = Week.objects.filter(pk=week_id, phase__plan=plan).first() if week_id else None
    return JsonResponse(_toggle_workout_complete(client, workout, week))


# --- Shared payload builders (used by both the client's own API above and
# the plan-scoped, trainer/owner/history API below, so "what a workout
# looks like" is defined exactly once) ---

def _note_list_payload(queryset):
    """Shared shape for Nutrient/Supplement rows sent down with the
    schedule -- both models have the same fields (see PlanNote), so this
    one function serializes either queryset."""
    return [
        {"id": n.id, "name": n.name, "amount": n.amount, "timing": n.timing, "notes": n.notes}
        for n in queryset
    ]


def _schedule_payload(plan, client):
    workouts = {
        w.id: {"name": w.name, "sub": w.sub, "flavor": w.flavor, "color": w.color}
        for w in Workout.objects.filter(plan=plan)
    }
    phases = [
        phase.to_dict(client=client)
        for phase in Phase.objects.filter(plan=plan).prefetch_related("weeks__days__workout")
    ]
    return {
        "workouts": workouts,
        "phases": phases,
        "nutrients": _note_list_payload(Nutrient.objects.filter(plan=plan)),
        "supplements": _note_list_payload(Supplement.objects.filter(plan=plan)),
    }


def _workout_payload(workout, client):
    exercises = list(workout.exercises.all())
    completed = {}
    workout_completed = False
    if client is not None:
        today = timezone.localdate()
        completions = CompletedSet.objects.filter(client=client, log_date=today, exercise__in=exercises)
        for c in completions:
            completed.setdefault(str(c.exercise_id), []).append(c.set_number)
        workout_completed = WorkoutCompletion.objects.filter(
            client=client, log_date=today, workout=workout
        ).exists()
    return {
        "id": workout.id,
        "name": workout.name,
        "sub": workout.sub,
        "flavor": workout.flavor,
        "color": workout.color,
        "exercises": [e.to_dict() for e in exercises],
        "completed": completed,
        "workout_completed": workout_completed,
    }


def _toggle_set(client, exercise, set_number):
    today = timezone.localdate()
    existing = CompletedSet.objects.filter(
        client=client, exercise=exercise, log_date=today, set_number=set_number
    ).first()
    if existing:
        existing.delete()
        return {"completed": False}
    CompletedSet.objects.create(client=client, exercise=exercise, log_date=today, set_number=set_number)
    return {"completed": True}


def _toggle_workout_complete(client, workout, week):
    today = timezone.localdate()
    existing = WorkoutCompletion.objects.filter(client=client, log_date=today, workout=workout).first()
    if existing:
        existing.delete()
        completed = False
    else:
        WorkoutCompletion.objects.create(client=client, log_date=today, workout=workout, week=week)
        completed = True
    response = {"completed": completed}
    if week is not None:
        response["week_tally"] = week.week_tally(client)
    return response


def _validate_exercise_payload(payload):
    """Shared validation for creating/editing an exercise -- returns
    (cleaned_fields, error_response_or_None)."""
    name = (payload.get("name") or "").strip()
    segment = payload.get("segment")
    if not name:
        return None, JsonResponse({"error": "Exercise name is required."}, status=400)
    if segment not in dict(Exercise.SEGMENT_CHOICES):
        return None, JsonResponse({"error": "Invalid segment."}, status=400)

    sets_count = payload.get("sets_count") or None
    rest_seconds = payload.get("rest_seconds") or None
    try:
        sets_count = int(sets_count) if sets_count not in (None, "") else None
        rest_seconds = int(rest_seconds) if rest_seconds not in (None, "") else None
    except (TypeError, ValueError):
        return None, JsonResponse({"error": "Sets and rest must be numbers."}, status=400)
    if sets_count is not None and not (1 <= sets_count <= 20):
        return None, JsonResponse({"error": "Sets must be between 1 and 20."}, status=400)
    if rest_seconds is not None and not (0 <= rest_seconds <= 3600):
        return None, JsonResponse({"error": "Rest must be between 0 and 3600 seconds."}, status=400)

    reps_text = (payload.get("reps_text") or "").strip()
    time_text = (payload.get("time_text") or "").strip()
    return {
        "name": name[:200],
        "segment": segment,
        "sets_count": sets_count,
        "reps_text": reps_text[:60],
        "rest_seconds": rest_seconds,
        "time_text": time_text[:20],
    }, None


# --- Plan-scoped API: read (trainer/owner editing, "client view" preview,
# and a client's own read-only history all share these two GET endpoints;
# only the front-end mode decides which controls render) ---

@login_required
@require_http_methods(["GET"])
def api_plan_schedule(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_view(request, plan)
    return JsonResponse(_schedule_payload(plan, _plan_owning_client(plan)))


@login_required
@require_http_methods(["GET"])
def api_plan_workout(request, plan_id, workout_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_view(request, plan)
    workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
    return JsonResponse(_workout_payload(workout, _plan_owning_client(plan)))


# --- Plan-scoped API: write (trainer/owner only -- exercise CRUD +
# reorder used to be reachable by any client on their own active plan;
# that gap is closed by requiring manage-permission here instead) ---

@login_required
@require_http_methods(["POST"])
def api_plan_create_exercise(request, plan_id, workout_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    fields, error = _validate_exercise_payload(payload)
    if error:
        return error

    last_order = workout.exercises.order_by("-order").values_list("order", flat=True).first() or 0
    exercise = Exercise.objects.create(
        workout=workout, order=last_order + 1, is_custom=True, created_by=request.user, **fields
    )
    return JsonResponse(exercise.to_dict(), status=201)


@login_required
@require_http_methods(["POST"])
def api_plan_reorder_exercises(request, plan_id, workout_id):
    """Persist a new exercise order for one workout after a drag-and-drop
    rearrange -- payload is {"order": [exercise_id, ...]} listing every one
    of this workout's exercises exactly once, in its new top-to-bottom
    order."""
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    order = payload.get("order")
    if not isinstance(order, list) or not order:
        return JsonResponse({"error": "order must be a non-empty list of exercise ids."}, status=400)
    try:
        ordered_ids = [int(exercise_id) for exercise_id in order]
    except (TypeError, ValueError):
        return JsonResponse({"error": "order must contain exercise ids."}, status=400)

    exercises = {e.id: e for e in workout.exercises.all()}
    if set(ordered_ids) != set(exercises.keys()) or len(ordered_ids) != len(exercises):
        return JsonResponse(
            {"error": "order must include exactly this workout's exercises, each once."}, status=400
        )

    for index, exercise_id in enumerate(ordered_ids):
        exercise = exercises[exercise_id]
        if exercise.order != index:
            exercise.order = index
            exercise.save(update_fields=["order"])

    return JsonResponse({"reordered": True})


@login_required
@require_http_methods(["DELETE", "PATCH"])
def api_plan_exercise_detail(request, plan_id, exercise_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    exercise = get_object_or_404(Exercise, pk=exercise_id, workout__plan=plan)

    if request.method == "DELETE":
        exercise.delete()
        return JsonResponse({"deleted": True})

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    fields, error = _validate_exercise_payload(payload)
    if error:
        return error
    for key, value in fields.items():
        setattr(exercise, key, value)
    exercise.save()
    return JsonResponse(exercise.to_dict())


# --- Trainer/Owner: Workouts & Phases structural editor, plan-scoped ---

@login_required
def plan_manage(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    workouts = Workout.objects.filter(plan=plan)
    phases = list(Phase.objects.filter(plan=plan).prefetch_related("weeks__days__workout"))
    nutrients = Nutrient.objects.filter(plan=plan)
    supplements = Supplement.objects.filter(plan=plan)
    return render(request, "training/plan_manage.html", {
        "plan": plan,
        "workouts": workouts,
        "phases": phases,
        "phase_count": len(phases),
        "max_phases": MAX_PHASES,
        "can_add_phase": len(phases) < MAX_PHASES,
        "nutrients": nutrients,
        "supplements": supplements,
    })


@login_required
def plan_workout_create(request, plan_id):
    """Creates a bare new Workout (a placeholder name, everything else at
    its model default) and drops the trainer straight onto its own edit
    page -- same page as workout_edit, exercise editor already live. No
    separate "fill in name/color, then add exercises on the next screen"
    form/page anymore: that used to mean two near-identical pages for one
    workout, so this collapsed to one. Renaming/recoloring happens on that
    same landing page via the form workout_edit already renders. POST-only
    (like week_create) so a plain GET/prefetch/back-navigation can't create
    a stray workout; any GET just bounces back to the Manage page."""
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    if request.method == "POST":
        last_order = (
            Workout.objects.filter(plan=plan).order_by("-order").values_list("order", flat=True).first() or 0
        )
        workout = Workout.objects.create(plan=plan, name="New Workout", order=last_order + 1)
        return redirect("workout_edit", workout_id=workout.id)
    return redirect("plan_manage", plan_id=plan.id)


@login_required
def workout_edit(request, workout_id):
    workout = get_object_or_404(Workout, pk=workout_id)
    _require_manage(request, workout.plan)
    if request.method == "POST":
        form = WorkoutForm(request.POST, instance=workout)
        if form.is_valid():
            form.save()
            return redirect("plan_manage", plan_id=workout.plan_id)
    else:
        form = WorkoutForm(instance=workout)
    return render(request, "training/workout_form.html", {
        "form": form, "workout": workout, "plan": workout.plan,
    })


@login_required
def workout_delete(request, workout_id):
    workout = get_object_or_404(Workout, pk=workout_id)
    _require_manage(request, workout.plan)
    if request.method == "POST":
        workout.delete()
        return redirect("plan_manage", plan_id=workout.plan_id)
    return render(request, "training/confirm_delete.html", {
        "object_label": f'the "{workout.name}" workout',
        "detail": "This also removes every exercise in it, and clears it from any day it's scheduled on.",
        "cancel_url": "plan_manage",
        "cancel_url_arg": workout.plan_id,
    })


# --- Trainer/Owner: Nutrients & Supplements reference lists, plan-scoped.
# Both are flat, ordered lists of read-only-to-the-client rows (no
# exercises/weeks nested underneath), so unlike Workouts they expose their
# `order` field directly on the form -- the same pattern Phase uses. ---

@login_required
def plan_nutrient_create(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    last_order = (
        Nutrient.objects.filter(plan=plan).order_by("-order").values_list("order", flat=True).first() or 0
    )
    if request.method == "POST":
        form = NutrientForm(request.POST)
        if form.is_valid():
            nutrient = form.save(commit=False)
            nutrient.plan = plan
            if not form.cleaned_data.get("order"):
                nutrient.order = last_order + 1
            nutrient.save()
            return redirect("plan_manage", plan_id=plan.id)
    else:
        form = NutrientForm(initial={"order": last_order + 1})
    return render(request, "training/nutrient_form.html", {"form": form, "is_new": True, "plan": plan})


@login_required
def nutrient_edit(request, nutrient_id):
    nutrient = get_object_or_404(Nutrient, pk=nutrient_id)
    plan = nutrient.plan
    _require_manage(request, plan)
    if request.method == "POST":
        form = NutrientForm(request.POST, instance=nutrient)
        if form.is_valid():
            form.save()
            return redirect("plan_manage", plan_id=plan.id)
    else:
        form = NutrientForm(instance=nutrient)
    return render(request, "training/nutrient_form.html", {
        "form": form, "is_new": False, "nutrient": nutrient, "plan": plan,
    })


@login_required
def nutrient_delete(request, nutrient_id):
    nutrient = get_object_or_404(Nutrient, pk=nutrient_id)
    plan = nutrient.plan
    _require_manage(request, plan)
    if request.method == "POST":
        nutrient.delete()
        return redirect("plan_manage", plan_id=plan.id)
    return render(request, "training/confirm_delete.html", {
        "object_label": f'the "{nutrient.name}" nutrient',
        "detail": "This removes it from the plan's reference list.",
        "cancel_url": "plan_manage",
        "cancel_url_arg": plan.id,
    })


@login_required
def plan_supplement_create(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    last_order = (
        Supplement.objects.filter(plan=plan).order_by("-order").values_list("order", flat=True).first() or 0
    )
    if request.method == "POST":
        form = SupplementForm(request.POST)
        if form.is_valid():
            supplement = form.save(commit=False)
            supplement.plan = plan
            if not form.cleaned_data.get("order"):
                supplement.order = last_order + 1
            supplement.save()
            return redirect("plan_manage", plan_id=plan.id)
    else:
        form = SupplementForm(initial={"order": last_order + 1})
    return render(request, "training/supplement_form.html", {"form": form, "is_new": True, "plan": plan})


@login_required
def supplement_edit(request, supplement_id):
    supplement = get_object_or_404(Supplement, pk=supplement_id)
    plan = supplement.plan
    _require_manage(request, plan)
    if request.method == "POST":
        form = SupplementForm(request.POST, instance=supplement)
        if form.is_valid():
            form.save()
            return redirect("plan_manage", plan_id=plan.id)
    else:
        form = SupplementForm(instance=supplement)
    return render(request, "training/supplement_form.html", {
        "form": form, "is_new": False, "supplement": supplement, "plan": plan,
    })


@login_required
def supplement_delete(request, supplement_id):
    supplement = get_object_or_404(Supplement, pk=supplement_id)
    plan = supplement.plan
    _require_manage(request, plan)
    if request.method == "POST":
        supplement.delete()
        return redirect("plan_manage", plan_id=plan.id)
    return render(request, "training/confirm_delete.html", {
        "object_label": f'the "{supplement.name}" supplement',
        "detail": "This removes it from the plan's reference list.",
        "cancel_url": "plan_manage",
        "cancel_url_arg": plan.id,
    })


def _save_week_days(week, post_data, plan):
    """Persist one week's Mon-Sun workout assignments from the phase_form
    POST. Any submitted workout id that doesn't belong to this same plan is
    dropped to a rest day instead of trusted verbatim -- a plan's schedule
    should never end up referencing another plan's workout."""
    prefix = f"day_week{week.id}_"
    valid_workout_ids = set(plan.workouts.values_list("id", flat=True))
    for weekday, _label in WeekDay.WEEKDAYS:
        raw = post_data.get(f"{prefix}{weekday}", "")
        workout_id = int(raw) if raw else None
        if workout_id is not None and workout_id not in valid_workout_ids:
            workout_id = None
        WeekDay.objects.update_or_create(
            week=week, weekday=weekday, defaults={"workout_id": workout_id}
        )


def _week_rows_context(weeks):
    """Builds the per-week weekday-grid rows phase_form.html renders, one
    set per week, keyed by that week's id so the POST field names round
    trip through _save_week_days above."""
    rows = []
    for week in weeks:
        day_assignments = {d.weekday: d.workout_id for d in week.days.all()}
        rows.append({
            "week": week,
            "day_rows": [(wd, label, day_assignments.get(wd)) for wd, label in WeekDay.WEEKDAYS],
        })
    return rows


@login_required
def plan_phase_create(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    if Phase.objects.filter(plan=plan).count() >= MAX_PHASES:
        return redirect("plan_manage", plan_id=plan.id)

    if request.method == "POST":
        form = PhaseForm(request.POST)
        if form.is_valid():
            last_order = (
                Phase.objects.filter(plan=plan).order_by("-order").values_list("order", flat=True).first() or 0
            )
            phase = form.save(commit=False)
            phase.plan = plan
            if not form.cleaned_data.get("order"):
                phase.order = last_order + 1
            phase.save()
            # A phase is only useful once it has at least one week to
            # configure, so start it off with one blank (all rest-day) week.
            Week.objects.create(phase=phase, order=1)
            return redirect("phase_edit", phase_id=phase.id)
    else:
        last_order = (
            Phase.objects.filter(plan=plan).order_by("-order").values_list("order", flat=True).first() or 0
        )
        form = PhaseForm(initial={"order": last_order + 1})
    return render(request, "training/phase_form.html", {
        "form": form, "is_new": True, "plan": plan,
        "workouts": Workout.objects.filter(plan=plan), "week_rows": [],
    })


@login_required
def phase_edit(request, phase_id):
    phase = get_object_or_404(Phase, pk=phase_id)
    plan = phase.plan
    _require_manage(request, plan)
    weeks = list(phase.weeks.prefetch_related("days__workout").all())
    if request.method == "POST":
        form = PhaseForm(request.POST, instance=phase)
        if form.is_valid():
            form.save()
            for week in weeks:
                _save_week_days(week, request.POST, plan)
            return redirect("plan_manage", plan_id=plan.id)
    else:
        form = PhaseForm(instance=phase)
    return render(request, "training/phase_form.html", {
        "form": form, "is_new": False, "phase": phase, "plan": plan,
        "workouts": Workout.objects.filter(plan=plan),
        "week_rows": _week_rows_context(weeks),
        "can_add_week": len(weeks) < MAX_WEEKS_PER_PHASE,
        "max_weeks": MAX_WEEKS_PER_PHASE,
    })


@login_required
def phase_delete(request, phase_id):
    phase = get_object_or_404(Phase, pk=phase_id)
    plan = phase.plan
    _require_manage(request, plan)
    if request.method == "POST":
        phase.delete()
        return redirect("plan_manage", plan_id=plan.id)
    return render(request, "training/confirm_delete.html", {
        "object_label": f'the "{phase.title}" phase',
        "detail": "Any other phase's week numbers will shift to fill the gap.",
        "cancel_url": "plan_manage",
        "cancel_url_arg": plan.id,
    })


@login_required
def week_create(request, phase_id):
    phase = get_object_or_404(Phase, pk=phase_id)
    plan = phase.plan
    _require_manage(request, plan)
    if request.method == "POST" and phase.weeks.count() < MAX_WEEKS_PER_PHASE:
        last_order = phase.weeks.order_by("-order").values_list("order", flat=True).first() or 0
        Week.objects.create(phase=phase, order=last_order + 1)
    return redirect("phase_edit", phase_id=phase.id)


@login_required
def week_delete(request, week_id):
    week = get_object_or_404(Week, pk=week_id)
    phase = week.phase
    _require_manage(request, phase.plan)
    # A phase always needs at least one week -- delete the phase instead if
    # you want to remove its last one.
    if phase.weeks.count() <= 1:
        return redirect("phase_edit", phase_id=phase.id)
    if request.method == "POST":
        week.delete()
        return redirect("phase_edit", phase_id=phase.id)
    return render(request, "training/confirm_delete.html", {
        "object_label": f'{week.label()} from the "{phase.title}" phase',
        "detail": "Later weeks in this phase will shift down to fill the gap.",
        "cancel_url": "phase_edit",
        "cancel_url_arg": phase.id,
    })


# --- Trainer/Owner: the live schedule/exercise editing view for one plan,
# and the read-only "Client view" preview of the same plan ---

def _plan_context(plan):
    client = _plan_owning_client(plan)
    assignment = plan.assignments.order_by("-assigned_at").first()
    return {
        "plan": plan,
        "owning_client": client,
        "assignment": assignment,
        "is_template": plan.is_library_template(),
    }


@login_required
def plan_detail(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    context = _plan_context(plan)
    context["mode"] = "trainer"
    return render(request, "training/plan_detail.html", context)


@login_required
def plan_preview(request, plan_id):
    """Read-only "Client view" -- shows a trainer/owner exactly what the
    plan's client would see, but nothing clicked here is saved (a
    disabled-input preview, not a second interactive surface writing into
    the client's real logged history)."""
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    context = _plan_context(plan)
    context["mode"] = "preview"
    return render(request, "training/plan_preview.html", context)


@login_required
def client_plan_history(request, assignment_id):
    """A client's own read-only view of one of their past (or current)
    plan assignments -- structure only, no set-checkboxes, since
    day-by-day completion tracking is only ever about "today"."""
    assignment = get_object_or_404(PlanAssignment, pk=assignment_id)
    plan = assignment.plan
    _require_view(request, plan)
    context = _plan_context(plan)
    context["mode"] = "history"
    context["viewing_own"] = True
    return render(request, "training/plan_preview.html", context)


# --- Trainer/Owner: plan library (templates) + clone-on-assign ---

@login_required
def plan_library(request, trainer_id):
    trainer = get_object_or_404(Trainer, pk=trainer_id)
    _require_manage_trainer(request, trainer)
    templates = Plan.objects.filter(trainer=trainer, assignments__isnull=True).distinct()
    return render(request, "training/plan_library.html", {"trainer": trainer, "templates": templates})


@login_required
def plan_delete(request, plan_id):
    """Trainer/owner only, and only for a plan that's never been assigned
    to a client -- once a client has (or ever had) their own copy, the
    original stays around as history and isn't deletable from here. This
    is strictly for library templates the trainer built and no longer
    wants, e.g. after replacing it with a newer version."""
    plan = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, plan)
    if not plan.is_library_template():
        raise Http404("This plan has been assigned to a client and can't be deleted.")
    trainer_id = plan.trainer_id
    if request.method == "POST":
        plan.delete()
        return redirect("plan_library", trainer_id=trainer_id)
    return render(request, "training/confirm_delete.html", {
        "object_label": f'the "{plan.name}" plan',
        "detail": "This permanently removes its workouts, phases, and exercises.",
        "cancel_url": "plan_library",
        "cancel_url_arg": trainer_id,
        "cancel_label": "Plan Library",
    })


@login_required
def plan_create(request, trainer_id):
    trainer = get_object_or_404(Trainer, pk=trainer_id)
    _require_manage_trainer(request, trainer)
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.trainer = trainer
            plan.save()
            return redirect("plan_manage", plan_id=plan.id)
    else:
        form = PlanForm()
    return render(request, "training/plan_form.html", {"form": form, "trainer": trainer})


@login_required
def plan_assign(request, plan_id):
    template = get_object_or_404(Plan, pk=plan_id)
    _require_manage(request, template)
    trainer = template.trainer

    if request.method == "POST":
        client_id = request.POST.get("client_id")
        client = get_object_or_404(Client, pk=client_id, trainer=trainer)
        new_plan = clone_plan_for_client(template, client)
        PlanAssignment.objects.filter(client=client, is_active=True).update(is_active=False)
        PlanAssignment.objects.create(plan=new_plan, client=client, is_active=True)
        return redirect("plan_detail", plan_id=new_plan.id)

    clients = trainer.clients.select_related("user").order_by("user__username")
    return render(request, "training/plan_assign.html", {"template": template, "clients": clients})


@login_required
@require_http_methods(["POST"])
def plan_unassign(request, assignment_id):
    assignment = get_object_or_404(PlanAssignment, pk=assignment_id)
    _require_manage(request, assignment.plan)
    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    return redirect("trainer_client_detail", client_id=assignment.client_id)
