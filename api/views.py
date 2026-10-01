"""JWT-only native-client API. Browser endpoints stay in ``training.views``."""

from datetime import date, timedelta

from django.conf import settings
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from accounts.models import Client, UserProfile
from training import completions
from training.completions import is_future_date, user_today
from training.models import CompletedSet, Exercise, PlanAssignment, Week, WeekDay, Workout, WorkoutCompletion

from .serializers import (
    ActivePlanSerializer,
    ClientWorkoutSerializer,
    CompletionSerializer,
    HistorySerializer,
    LogoutSerializer,
    MeSerializer,
    MeUpdateSerializer,
    ScheduleSerializer,
    SyncEventSerializer,
    SyncRequestSerializer,
    SyncResponseSerializer,
    WorkoutTimingSerializer,
)

DATE_PARAM = OpenApiParameter(
    "date",
    OpenApiTypes.DATE,
    description="The user's local calendar day (YYYY-MM-DD). Defaults to today in the user's time zone.",
)
MAX_HISTORY_DAYS = 366


def parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: ["Use YYYY-MM-DD."]}) from exc


def requested_date(request):
    """?date= if given (validated, not in the future), else the user's today."""
    raw = request.query_params.get("date")
    if raw is None:
        return user_today(request.user)
    value = parse_date(raw, "date")
    if is_future_date(request.user, value):
        raise ValidationError({"date": ["Cannot be in the future."]})
    return value


def active_context(user):
    """Return this user's client and active assignment, or the API's 404 boundary."""
    try:
        client = user.client_profile
    except Client.DoesNotExist as exc:
        raise NotFound("No client profile is associated with this account.") from exc
    assignment = (
        PlanAssignment.objects.filter(client=client, is_active=True)
        .select_related("plan", "plan__trainer", "plan__trainer__gym")
        .first()
    )
    if assignment is None:
        raise NotFound("No active plan is assigned to this client.")
    return client, assignment


def note_payload(notes):
    return [
        {"id": note.id, "name": note.name, "amount": note.amount, "timing": note.timing, "notes": note.notes}
        for note in notes
    ]


def workout_summary(workout):
    return {
        "id": workout.id,
        "name": workout.name,
        "sub": workout.sub,
        "flavor": workout.flavor,
        "color": workout.color,
        "order": workout.order,
    }


def tally_payload(week, client, on_date):
    return week.week_tally(client, on_date=on_date)


def schedule_payload(plan, client, on_date):
    phases = []
    weekday_order = {name: index for index, (name, _) in enumerate(WeekDay.WEEKDAYS)}
    for phase in plan.phases.prefetch_related("weeks__days__workout").all():
        weeks = []
        for week in phase.weeks.all():
            days = sorted(week.days.all(), key=lambda day: weekday_order[day.weekday])
            weeks.append(
                {
                    "id": week.id,
                    "order": week.order,
                    "number": week.global_number(),
                    "label": week.label(),
                    "week_tally": tally_payload(week, client, on_date),
                    "days": [
                        {
                            "weekday": day.weekday,
                            "workout": workout_summary(day.workout) if day.workout else None,
                        }
                        for day in days
                    ],
                }
            )
        phases.append(
            {
                "id": phase.id,
                "title": phase.title,
                "note": phase.note,
                "order": phase.order,
                "number": phase.number(),
                "weeks": weeks,
            }
        )
    return {
        "date": on_date.isoformat(),
        "plan": {"id": plan.id, "name": plan.name, "description": plan.description},
        "phases": phases,
        "nutrients": note_payload(plan.nutrients.all()),
        "supplements": note_payload(plan.supplements.all()),
    }


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={204: None, 400: OpenApiResponse(description="Invalid refresh token.")})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError as exc:
            raise ValidationError({"refresh": ["Invalid or expired refresh token."]}) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses={200: MeSerializer})
    def get(self, request):
        return Response(self.payload(request.user))

    @extend_schema(request=MeUpdateSerializer, responses={200: MeSerializer})
    def patch(self, request):
        serializer = MeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.timezone = serializer.validated_data["timezone"]
        profile.save(update_fields=["timezone"])
        request.user.profile = profile
        return Response(self.payload(request.user))

    @staticmethod
    def payload(user):
        roles = []
        if user.owned_gyms.exists():
            roles.append("owner")
        trainer = getattr(user, "trainer_profile", None)
        client = getattr(user, "client_profile", None)
        if trainer:
            roles.append("trainer")
        if client:
            roles.append("client")
        profile = UserProfile.objects.filter(user=user).first()
        return {
            "id": user.id,
            "username": user.get_username(),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "roles": roles,
            "client_id": client.id if client else None,
            "trainer_id": trainer.id if trainer else None,
            "gym_id": (client.trainer.gym_id if client else trainer.gym_id if trainer else None),
            "owned_gym_ids": list(user.owned_gyms.values_list("id", flat=True)),
            "timezone": profile.timezone if profile else settings.TIME_ZONE,
            "today": user_today(user).isoformat(),
        }


class ActivePlanView(APIView):
    @extend_schema(responses={200: ActivePlanSerializer})
    def get(self, request):
        client, assignment = active_context(request.user)
        plan = assignment.plan
        return Response(
            {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "assignment": {
                    "id": assignment.id,
                    "client_id": client.id,
                    "assigned_at": assignment.assigned_at,
                    "is_active": assignment.is_active,
                    "trainer_id": plan.trainer_id,
                    "gym_id": plan.trainer.gym_id,
                },
            }
        )


class ActiveScheduleView(APIView):
    @extend_schema(parameters=[DATE_PARAM], responses={200: ScheduleSerializer})
    def get(self, request):
        client, assignment = active_context(request.user)
        return Response(schedule_payload(assignment.plan, client, requested_date(request)))


class WorkoutView(APIView):
    @extend_schema(parameters=[DATE_PARAM], responses={200: ClientWorkoutSerializer})
    def get(self, request, workout_id):
        client, assignment = active_context(request.user)
        on_date = requested_date(request)
        try:
            workout = Workout.objects.prefetch_related("exercises").get(pk=workout_id, plan=assignment.plan)
        except Workout.DoesNotExist as exc:
            raise Http404 from exc
        exercises = list(workout.exercises.all())
        completed = CompletedSet.objects.filter(client=client, exercise__in=exercises, log_date=on_date)
        completed_by_exercise = {}
        for completion in completed:
            completed_by_exercise.setdefault(completion.exercise_id, []).append(completion.set_number)
        completion = WorkoutCompletion.objects.filter(client=client, workout=workout, log_date=on_date).first()
        return Response(
            {
                **workout_summary(workout),
                "date": on_date.isoformat(),
                "exercises": [
                    {
                        "id": exercise.id,
                        "segment": exercise.segment,
                        "name": exercise.name,
                        "sets_count": exercise.sets_count,
                        "reps_text": exercise.reps_text,
                        "rest_seconds": exercise.rest_seconds,
                        "time_text": exercise.time_text,
                        "order": exercise.order,
                        "completed_set_numbers": sorted(completed_by_exercise.get(exercise.id, [])),
                    }
                    for exercise in exercises
                ],
                "workout_completed": completion is not None,
                "started_at": completion.started_at if completion else None,
                "ended_at": completion.ended_at if completion else None,
            }
        )


class SetCompletionView(GenericAPIView):
    serializer_class = CompletionSerializer

    def exercise(self, user, exercise_id, set_number):
        client, assignment = active_context(user)
        try:
            exercise = Exercise.objects.get(pk=exercise_id, workout__plan=assignment.plan)
        except Exercise.DoesNotExist as exc:
            raise Http404 from exc
        maximum = exercise.sets_count or 1
        if set_number < 1 or set_number > maximum:
            raise ValidationError({"set_number": [f"Must be between 1 and {maximum} for this exercise."]})
        return client, exercise

    @extend_schema(
        parameters=[DATE_PARAM],
        responses={200: CompletionSerializer, 400: OpenApiResponse(description="Invalid set number.")},
    )
    def put(self, request, exercise_id, set_number):
        client, exercise = self.exercise(request.user, exercise_id, set_number)
        completions.set_completion(client, exercise, set_number, requested_date(request), True)
        return Response({"completed": True})

    @extend_schema(
        parameters=[DATE_PARAM],
        responses={200: CompletionSerializer, 400: OpenApiResponse(description="Invalid set number.")},
    )
    def delete(self, request, exercise_id, set_number):
        client, exercise = self.exercise(request.user, exercise_id, set_number)
        completions.set_completion(client, exercise, set_number, requested_date(request), False)
        return Response({"completed": False})


class WorkoutCompletionView(GenericAPIView):
    serializer_class = CompletionSerializer

    @extend_schema(
        parameters=[DATE_PARAM],
        request=WorkoutTimingSerializer,
        responses={200: CompletionSerializer, 400: OpenApiResponse(description="Workout is not scheduled in week.")},
    )
    def put(self, request, week_id, workout_id):
        client, week, workout = workout_context(request.user, week_id, workout_id)
        timing = WorkoutTimingSerializer(data=request.data or {})
        timing.is_valid(raise_exception=True)
        on_date = requested_date(request)
        completions.workout_completion(client, workout, on_date, True, week=week, **timing.validated_data)
        return Response({"completed": True, "week_tally": tally_payload(week, client, on_date)})

    @extend_schema(
        parameters=[DATE_PARAM],
        responses={200: CompletionSerializer, 400: OpenApiResponse(description="Workout is not scheduled in week.")},
    )
    def delete(self, request, week_id, workout_id):
        client, week, workout = workout_context(request.user, week_id, workout_id)
        on_date = requested_date(request)
        completions.workout_completion(client, workout, on_date, False, week=week)
        return Response({"completed": False, "week_tally": tally_payload(week, client, on_date)})


def workout_context(user, week_id, workout_id, require_scheduled=True):
    client, assignment = active_context(user)
    try:
        workout = Workout.objects.get(pk=workout_id, plan=assignment.plan)
        week = Week.objects.get(pk=week_id, phase__plan=assignment.plan) if week_id is not None else None
    except (Week.DoesNotExist, Workout.DoesNotExist) as exc:
        raise Http404 from exc
    if require_scheduled and week is not None and not WeekDay.objects.filter(week=week, workout=workout).exists():
        raise ValidationError({"workout_id": ["This workout is not scheduled in this week."]})
    return client, week, workout


class HistoryView(APIView):
    """Finished workouts between two dates (inclusive), newest first, with a
    count of checked sets per day -- the basis for history/streak screens."""

    @extend_schema(
        parameters=[
            OpenApiParameter("from", OpenApiTypes.DATE, required=True),
            OpenApiParameter("to", OpenApiTypes.DATE, required=True),
        ],
        responses={200: HistorySerializer},
    )
    def get(self, request):
        client, _ = active_context(request.user)
        start = parse_date(request.query_params.get("from"), "from")
        end = parse_date(request.query_params.get("to"), "to")
        if end < start:
            raise ValidationError({"to": ["Must not be before from."]})
        if end - start > timedelta(days=MAX_HISTORY_DAYS):
            raise ValidationError({"to": [f"Range may span at most {MAX_HISTORY_DAYS} days."]})
        rows = WorkoutCompletion.objects.filter(client=client, log_date__range=(start, end)).select_related("workout")
        set_counts = {}
        for log_date in CompletedSet.objects.filter(client=client, log_date__range=(start, end)).values_list(
            "log_date", flat=True
        ):
            set_counts[log_date] = set_counts.get(log_date, 0) + 1
        return Response(
            {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "workouts": [
                    {
                        "date": row.log_date.isoformat(),
                        "workout": workout_summary(row.workout),
                        "week_id": row.week_id,
                        "completed_at": row.completed_at,
                        "started_at": row.started_at,
                        "ended_at": row.ended_at,
                    }
                    for row in rows
                ],
                "sets_completed_by_date": {d.isoformat(): n for d, n in sorted(set_counts.items(), reverse=True)},
            }
        )


class SyncView(APIView):
    """Apply a batch of queued offline changes.

    Each event gets its own result: ``applied``; ``duplicate`` (this id was
    already received -- safe to drop from the device queue); ``stale`` (a
    newer change to the same set/workout/day already won); or ``rejected``
    with ``errors`` (bad input or not part of the active plan -- retrying
    won't help). Every status except a network failure means the device can
    remove the event from its queue."""

    @extend_schema(request=SyncRequestSerializer, responses={200: SyncResponseSerializer})
    def post(self, request):
        batch = SyncRequestSerializer(data=request.data)
        batch.is_valid(raise_exception=True)
        client, assignment = active_context(request.user)
        results, valid = {}, []
        for index, raw in enumerate(batch.validated_data["events"]):
            event = SyncEventSerializer(data=raw)
            key = str(raw.get("id", f"index:{index}"))
            if not event.is_valid():
                results[index] = {"id": key, "status": "rejected", "errors": event.errors}
                continue
            valid.append((index, event.validated_data))
        # Apply in the order things happened on the device.
        for index, data in sorted(valid, key=lambda item: item[1]["occurred_at"]):
            results[index] = {"id": str(data["id"]), **self.apply(request.user, client, assignment, data)}
        return Response({"results": [results[i] for i in sorted(results)]})

    @staticmethod
    def apply(user, client, assignment, data):
        if is_future_date(user, data["log_date"]):
            return {"status": "rejected", "errors": {"log_date": ["Cannot be in the future."]}}
        common = {"occurred_at": data["occurred_at"], "event_id": data["id"]}
        try:
            if data["type"].startswith("set_"):
                exercise = Exercise.objects.get(pk=data["exercise_id"], workout__plan=assignment.plan)
                if data["set_number"] > (exercise.sets_count or 1):
                    return {"status": "rejected", "errors": {"set_number": ["Out of range for this exercise."]}}
                status_ = completions.set_completion(
                    client, exercise, data["set_number"], data["log_date"], data["type"] == "set_completed", **common
                )
            else:
                completed = data["type"] == "workout_completed"
                _, week, workout = workout_context(
                    user, data.get("week_id"), data["workout_id"], require_scheduled=completed
                )
                timing = {"started_at": data.get("started_at"), "ended_at": data.get("ended_at")} if completed else {}
                status_ = completions.workout_completion(
                    client, workout, data["log_date"], completed, week=week, **timing, **common
                )
        except (Exercise.DoesNotExist, Http404):
            return {"status": "rejected", "errors": {"detail": ["Not part of your active plan."]}}
        except ValidationError as exc:
            return {"status": "rejected", "errors": exc.detail}
        return {"status": status_}
