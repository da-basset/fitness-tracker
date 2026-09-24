"""JWT-only native-client API. Browser endpoints stay in ``training.views``."""

from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from accounts.models import Client
from training.models import CompletedSet, Exercise, PlanAssignment, Week, WeekDay, Workout, WorkoutCompletion

from .serializers import CompletionSerializer, LogoutSerializer


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


def tally_payload(week, client):
    return week.week_tally(client)


def schedule_payload(plan, client):
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
                    "week_tally": tally_payload(week, client),
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
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        user = request.user
        roles = []
        if user.owned_gyms.exists():
            roles.append("owner")
        trainer = getattr(user, "trainer_profile", None)
        client = getattr(user, "client_profile", None)
        if trainer:
            roles.append("trainer")
        if client:
            roles.append("client")
        return Response(
            {
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
            }
        )


class ActivePlanView(APIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
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
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        client, assignment = active_context(request.user)
        return Response(schedule_payload(assignment.plan, client))


class WorkoutView(APIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request, workout_id):
        client, assignment = active_context(request.user)
        try:
            workout = Workout.objects.prefetch_related("exercises").get(pk=workout_id, plan=assignment.plan)
        except Workout.DoesNotExist as exc:
            raise Http404 from exc
        exercises = list(workout.exercises.all())
        completed = CompletedSet.objects.filter(client=client, exercise__in=exercises, log_date=timezone.localdate())
        completed_by_exercise = {}
        for completion in completed:
            completed_by_exercise.setdefault(completion.exercise_id, []).append(completion.set_number)
        return Response(
            {
                **workout_summary(workout),
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
                "workout_completed": WorkoutCompletion.objects.filter(
                    client=client, workout=workout, log_date=timezone.localdate()
                ).exists(),
            }
        )


class SetCompletionView(GenericAPIView):
    serializer_class = CompletionSerializer
    @extend_schema(responses={200: CompletionSerializer, 400: OpenApiResponse(description="Invalid set number.")})
    def put(self, request, exercise_id, set_number):
        client, assignment = active_context(request.user)
        try:
            exercise = Exercise.objects.get(pk=exercise_id, workout__plan=assignment.plan)
        except Exercise.DoesNotExist as exc:
            raise Http404 from exc
        maximum = exercise.sets_count or 1
        if set_number < 1 or set_number > maximum:
            raise ValidationError({"set_number": [f"Must be between 1 and {maximum} for this exercise."]})
        CompletedSet.objects.get_or_create(
            client=client, exercise=exercise, log_date=timezone.localdate(), set_number=set_number
        )
        return Response({"completed": True})

    @extend_schema(responses={200: CompletionSerializer, 400: OpenApiResponse(description="Invalid set number.")})
    def delete(self, request, exercise_id, set_number):
        client, assignment = active_context(request.user)
        try:
            exercise = Exercise.objects.get(pk=exercise_id, workout__plan=assignment.plan)
        except Exercise.DoesNotExist as exc:
            raise Http404 from exc
        maximum = exercise.sets_count or 1
        if set_number < 1 or set_number > maximum:
            raise ValidationError({"set_number": [f"Must be between 1 and {maximum} for this exercise."]})
        CompletedSet.objects.filter(
            client=client, exercise=exercise, log_date=timezone.localdate(), set_number=set_number
        ).delete()
        return Response({"completed": False})


class WorkoutCompletionView(GenericAPIView):
    serializer_class = CompletionSerializer
    @extend_schema(responses={200: CompletionSerializer, 400: OpenApiResponse(description="Workout is not scheduled in week.")})
    def put(self, request, week_id, workout_id):
        client, _, week, workout = self.context(request.user, week_id, workout_id)
        WorkoutCompletion.objects.get_or_create(
            client=client, workout=workout, log_date=timezone.localdate(), defaults={"week": week}
        )
        return Response({"completed": True, "week_tally": tally_payload(week, client)})

    @extend_schema(
        responses={200: CompletionSerializer, 400: OpenApiResponse(description="Workout is not scheduled in week.")}
    )
    def delete(self, request, week_id, workout_id):
        client, _, week, workout = self.context(request.user, week_id, workout_id)
        WorkoutCompletion.objects.filter(client=client, workout=workout, log_date=timezone.localdate()).delete()
        return Response({"completed": False, "week_tally": tally_payload(week, client)})

    @staticmethod
    def context(user, week_id, workout_id):
        client, assignment = active_context(user)
        try:
            week = Week.objects.get(pk=week_id, phase__plan=assignment.plan)
            workout = Workout.objects.get(pk=workout_id, plan=assignment.plan)
        except (Week.DoesNotExist, Workout.DoesNotExist) as exc:
            raise Http404 from exc
        if not WeekDay.objects.filter(week=week, workout=workout).exists():
            raise ValidationError({"workout_id": ["This workout is not scheduled in this week."]})
        return client, assignment, week, workout
