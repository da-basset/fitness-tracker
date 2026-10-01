"""Trainer/owner management API: the native counterpart of the web app's
owner, trainer, plan library and plan editor pages.

Every view resolves its Plan or Trainer through the same rule the web app
uses (``accounts.permissions.can_manage_trainer``) and answers 404 when the
user has no access, so the two surfaces can't drift on who may do what."""

from django.db import transaction
from django.db.models import Max, Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Client, Gym, Trainer
from accounts.permissions import can_manage_trainer
from training.models import (
    MAX_PHASES,
    MAX_WEEKS_PER_PHASE,
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
from training.services import clone_plan_for_client

from .manage_serializers import (
    AccountCreateSerializer,
    AssignmentSerializer,
    AssignRequestSerializer,
    ClientDetailSerializer,
    ClientSummarySerializer,
    ExerciseSerializer,
    NutrientSerializer,
    PhaseSerializer,
    PlanDetailSerializer,
    PlanSummarySerializer,
    ReorderRequestSerializer,
    SupplementSerializer,
    TrainerSerializer,
    WeekDaysSerializer,
    WeekSerializer,
    WorkoutSerializer,
    display_name,
)

NO_ACCESS = "Not found."


# --- Access boundaries -------------------------------------------------------

def owned_gym(user):
    return Gym.objects.filter(owner=user).first()


def managed_trainer(user, trainer_id):
    trainer = Trainer.objects.select_related("gym", "user").filter(pk=trainer_id).first()
    if trainer is None or not can_manage_trainer(user, trainer):
        raise NotFound(NO_ACCESS)
    return trainer


def visible_trainers(user):
    """Owner: every trainer at their gym. Trainer: just themselves."""
    gym = owned_gym(user)
    if gym is not None:
        return Trainer.objects.filter(gym=gym)
    return Trainer.objects.filter(user=user)


def managed_plan(user, plan_id):
    plan = Plan.objects.select_related("trainer__gym").filter(pk=plan_id).first()
    if plan is None or not can_manage_trainer(user, plan.trainer):
        raise NotFound(NO_ACCESS)
    return plan


def viewable_plan(user, plan_id):
    """Managers, plus any client the plan is (or was) assigned to."""
    plan = Plan.objects.select_related("trainer__gym").filter(pk=plan_id).first()
    if plan is None:
        raise NotFound(NO_ACCESS)
    if can_manage_trainer(user, plan.trainer) or plan.assignments.filter(client__user=user).exists():
        return plan
    raise NotFound(NO_ACCESS)


def managed_client(user, client_id):
    client = Client.objects.select_related("user", "trainer__gym", "trainer__user").filter(pk=client_id).first()
    if client is None or not can_manage_trainer(user, client.trainer):
        raise NotFound(NO_ACCESS)
    return client


def next_order(queryset):
    return (queryset.aggregate(top=Max("order"))["top"] or 0) + 1


def clients_queryset():
    return Client.objects.select_related("user", "trainer__user").prefetch_related(
        Prefetch("plan_assignments", queryset=PlanAssignment.objects.select_related("plan"))
    )


def plan_detail(plan, user):
    assignment = plan.assignments.select_related("plan", "client__user").order_by("-assigned_at").first()
    data = {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "trainer_id": plan.trainer_id,
        "source_plan_id": plan.source_plan_id,
        "created_at": plan.created_at,
        "is_template": assignment is None,
        "can_manage": can_manage_trainer(user, plan.trainer),
        "owning_client": (
            {"id": assignment.client_id, "name": display_name(assignment.client.user)} if assignment else None
        ),
        "assignment": assignment,
        "workouts": plan.workouts.prefetch_related("exercises"),
        "phases": plan.phases.prefetch_related("weeks__days"),
        "nutrients": plan.nutrients.all(),
        "supplements": plan.supplements.all(),
        "limits": {"max_phases": MAX_PHASES, "max_weeks_per_phase": MAX_WEEKS_PER_PHASE},
    }
    return PlanDetailSerializer(data).data


# --- Owner: trainers ---------------------------------------------------------

class TrainerListView(APIView):
    @extend_schema(responses={200: TrainerSerializer(many=True)})
    def get(self, request):
        trainers = visible_trainers(request.user).select_related("user").order_by("user__username")
        return Response(TrainerSerializer(trainers, many=True).data)

    @extend_schema(request=AccountCreateSerializer, responses={201: TrainerSerializer})
    def post(self, request):
        gym = owned_gym(request.user)
        if gym is None:
            raise PermissionDenied("Only a gym owner can add trainers.")
        serializer = AccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trainer = Trainer.objects.create(user=serializer.save(), gym=gym)
        return Response(TrainerSerializer(trainer).data, status=status.HTTP_201_CREATED)


# --- Trainer: clients --------------------------------------------------------

class ClientListView(APIView):
    @extend_schema(responses={200: ClientSummarySerializer(many=True)})
    def get(self, request):
        clients = clients_queryset().filter(trainer__in=visible_trainers(request.user))
        return Response(ClientSummarySerializer(clients.order_by("user__username"), many=True).data)

    @extend_schema(request=AccountCreateSerializer, responses={201: ClientSummarySerializer})
    def post(self, request):
        trainer = Trainer.objects.filter(user=request.user).first()
        if trainer is None:
            raise PermissionDenied("Only a trainer can add clients.")
        serializer = AccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            client = Client.objects.create(user=serializer.save(), trainer=trainer)
        return Response(ClientSummarySerializer(clients_queryset().get(pk=client.pk)).data, status=status.HTTP_201_CREATED)


class ClientDetailView(APIView):
    @extend_schema(responses={200: ClientDetailSerializer})
    def get(self, request, client_id):
        client = managed_client(request.user, client_id)
        client = clients_queryset().get(pk=client.pk)
        assignments = list(client.plan_assignments.all())
        active = next((a for a in assignments if a.is_active), None)
        stats = None
        if active is not None:
            done = WorkoutCompletion.objects.filter(client=client, workout__plan=active.plan)
            stats = {
                "all_time_completed": done.count(),
                "last_completed_at": done.order_by("-log_date").values_list("log_date", flat=True).first(),
            }
        client.active_assignment = active
        client.past_assignments = sorted(
            (a for a in assignments if not a.is_active), key=lambda a: a.assigned_at, reverse=True
        )
        client.stats = stats
        client.templates = Plan.objects.filter(trainer=client.trainer, assignments__isnull=True).distinct()
        return Response(ClientDetailSerializer(client).data)


# --- Plan library ------------------------------------------------------------

class PlanLibraryView(APIView):
    @extend_schema(responses={200: PlanSummarySerializer(many=True)})
    def get(self, request, trainer_id):
        trainer = managed_trainer(request.user, trainer_id)
        templates = Plan.objects.filter(trainer=trainer, assignments__isnull=True).distinct()
        return Response(PlanSummarySerializer(templates, many=True).data)

    @extend_schema(request=PlanSummarySerializer, responses={201: PlanSummarySerializer})
    def post(self, request, trainer_id):
        trainer = managed_trainer(request.user, trainer_id)
        serializer = PlanSummarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = Plan.objects.create(trainer=trainer, **serializer.validated_data)
        return Response(PlanSummarySerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    @extend_schema(responses={200: PlanDetailSerializer})
    def get(self, request, plan_id):
        return Response(plan_detail(viewable_plan(request.user, plan_id), request.user))

    @extend_schema(responses={204: None, 400: OpenApiResponse(description="Plan has been assigned.")})
    def delete(self, request, plan_id):
        plan = managed_plan(request.user, plan_id)
        if not plan.is_library_template():
            raise ValidationError({"detail": ["This plan has been assigned to a client and can't be deleted."]})
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlanAssignView(APIView):
    @extend_schema(request=AssignRequestSerializer, responses={201: AssignmentSerializer})
    def post(self, request, plan_id):
        template = managed_plan(request.user, plan_id)
        serializer = AssignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = Client.objects.filter(pk=serializer.validated_data["client_id"], trainer=template.trainer).first()
        if client is None:
            raise ValidationError({"client_id": ["Not one of this plan's trainer's clients."]})
        with transaction.atomic():
            new_plan = clone_plan_for_client(template, client)
            PlanAssignment.objects.filter(client=client, is_active=True).update(is_active=False)
            assignment = PlanAssignment.objects.create(plan=new_plan, client=client, is_active=True)
        return Response(AssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class UnassignView(APIView):
    @extend_schema(request=None, responses={200: AssignmentSerializer})
    def post(self, request, assignment_id):
        assignment = PlanAssignment.objects.select_related("plan__trainer__gym").filter(pk=assignment_id).first()
        if assignment is None or not can_manage_trainer(request.user, assignment.plan.trainer):
            raise NotFound(NO_ACCESS)
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        return Response(AssignmentSerializer(assignment).data)


# --- Plan editor -------------------------------------------------------------

class PlanChildView(APIView):
    """Base for plan-scoped create/update/delete of one model."""

    model = None
    serializer_class = None
    lookup = None  # URL kwarg naming the child's id

    def child(self, plan, pk):
        filters = {"pk": pk, **self.plan_filter(plan)}
        return get_object_or_404(self.model, **filters)

    def plan_filter(self, plan):
        return {"plan": plan}

    def update(self, request, plan_id, **kwargs):
        plan = managed_plan(request.user, plan_id)
        obj = self.child(plan, kwargs[self.lookup])
        serializer = self.serializer_class(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, plan_id, **kwargs):
        plan = managed_plan(request.user, plan_id)
        self.child(plan, kwargs[self.lookup]).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkoutCreateView(APIView):
    @extend_schema(request=WorkoutSerializer, responses={201: WorkoutSerializer})
    def post(self, request, plan_id):
        plan = managed_plan(request.user, plan_id)
        serializer = WorkoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.setdefault("order", next_order(plan.workouts))
        serializer.save(plan=plan)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkoutEditView(PlanChildView):
    model, serializer_class, lookup = Workout, WorkoutSerializer, "workout_id"

    @extend_schema(request=WorkoutSerializer, responses={200: WorkoutSerializer})
    def patch(self, request, plan_id, workout_id):
        return self.update(request, plan_id, workout_id=workout_id)

    @extend_schema(responses={204: None})
    def delete(self, request, plan_id, workout_id):
        return self.destroy(request, plan_id, workout_id=workout_id)


class ExerciseCreateView(APIView):
    @extend_schema(request=ExerciseSerializer, responses={201: ExerciseSerializer})
    def post(self, request, plan_id, workout_id):
        plan = managed_plan(request.user, plan_id)
        workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
        serializer = ExerciseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            workout=workout, order=next_order(workout.exercises), is_custom=True, created_by=request.user
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExerciseReorderView(APIView):
    @extend_schema(request=ReorderRequestSerializer, responses={200: ExerciseSerializer(many=True)})
    def post(self, request, plan_id, workout_id):
        plan = managed_plan(request.user, plan_id)
        workout = get_object_or_404(Workout, pk=workout_id, plan=plan)
        serializer = ReorderRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ordered_ids = serializer.validated_data["order"]
        exercises = {exercise.id: exercise for exercise in workout.exercises.all()}
        if len(ordered_ids) != len(exercises) or set(ordered_ids) != set(exercises):
            raise ValidationError({"order": ["Must list exactly this workout's exercises, each once."]})
        with transaction.atomic():
            for index, exercise_id in enumerate(ordered_ids):
                exercise = exercises[exercise_id]
                if exercise.order != index:
                    exercise.order = index
                    exercise.save(update_fields=["order"])
        return Response(ExerciseSerializer(workout.exercises.all(), many=True).data)


class ExerciseEditView(PlanChildView):
    model, serializer_class, lookup = Exercise, ExerciseSerializer, "exercise_id"

    def plan_filter(self, plan):
        return {"workout__plan": plan}

    @extend_schema(request=ExerciseSerializer, responses={200: ExerciseSerializer})
    def patch(self, request, plan_id, exercise_id):
        return self.update(request, plan_id, exercise_id=exercise_id)

    @extend_schema(responses={204: None})
    def delete(self, request, plan_id, exercise_id):
        return self.destroy(request, plan_id, exercise_id=exercise_id)


class PhaseCreateView(APIView):
    @extend_schema(request=PhaseSerializer, responses={201: PhaseSerializer})
    def post(self, request, plan_id):
        plan = managed_plan(request.user, plan_id)
        if plan.phases.count() >= MAX_PHASES:
            raise ValidationError({"detail": [f"A plan can have at most {MAX_PHASES} phases."]})
        serializer = PhaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.setdefault("order", next_order(plan.phases))
        with transaction.atomic():
            phase = serializer.save(plan=plan)
            # Like the web editor: a phase starts with one all-rest week.
            Week.objects.create(phase=phase, order=1)
        return Response(PhaseSerializer(phase).data, status=status.HTTP_201_CREATED)


class PhaseEditView(PlanChildView):
    model, serializer_class, lookup = Phase, PhaseSerializer, "phase_id"

    @extend_schema(request=PhaseSerializer, responses={200: PhaseSerializer})
    def patch(self, request, plan_id, phase_id):
        return self.update(request, plan_id, phase_id=phase_id)

    @extend_schema(responses={204: None})
    def delete(self, request, plan_id, phase_id):
        return self.destroy(request, plan_id, phase_id=phase_id)


class WeekCreateView(APIView):
    @extend_schema(request=None, responses={201: WeekSerializer})
    def post(self, request, plan_id, phase_id):
        plan = managed_plan(request.user, plan_id)
        phase = get_object_or_404(Phase, pk=phase_id, plan=plan)
        if phase.weeks.count() >= MAX_WEEKS_PER_PHASE:
            raise ValidationError({"detail": [f"A phase can have at most {MAX_WEEKS_PER_PHASE} weeks."]})
        week = Week.objects.create(phase=phase, order=next_order(phase.weeks))
        return Response(WeekSerializer(week).data, status=status.HTTP_201_CREATED)


class WeekEditView(APIView):
    def week(self, request, plan_id, week_id):
        plan = managed_plan(request.user, plan_id)
        return plan, get_object_or_404(Week.objects.select_related("phase"), pk=week_id, phase__plan=plan)

    @extend_schema(request=WeekDaysSerializer, responses={200: WeekSerializer})
    def patch(self, request, plan_id, week_id):
        plan, week = self.week(request, plan_id, week_id)
        serializer = WeekDaysSerializer(data=request.data, context={"plan": plan})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            for weekday, workout_id in serializer.validated_data["days"].items():
                WeekDay.objects.update_or_create(week=week, weekday=weekday, defaults={"workout_id": workout_id})
        return Response(WeekSerializer(week).data)

    @extend_schema(responses={204: None, 400: OpenApiResponse(description="A phase needs at least one week.")})
    def delete(self, request, plan_id, week_id):
        _, week = self.week(request, plan_id, week_id)
        if week.phase.weeks.count() <= 1:
            raise ValidationError({"detail": ["A phase needs at least one week. Delete the phase instead."]})
        week.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NoteCreateView(APIView):
    model = serializer_class = None

    def create(self, request, plan_id):
        plan = managed_plan(request.user, plan_id)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.setdefault("order", next_order(self.model.objects.filter(plan=plan)))
        serializer.save(plan=plan)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NutrientCreateView(NoteCreateView):
    model, serializer_class = Nutrient, NutrientSerializer

    @extend_schema(request=NutrientSerializer, responses={201: NutrientSerializer})
    def post(self, request, plan_id):
        return self.create(request, plan_id)


class SupplementCreateView(NoteCreateView):
    model, serializer_class = Supplement, SupplementSerializer

    @extend_schema(request=SupplementSerializer, responses={201: SupplementSerializer})
    def post(self, request, plan_id):
        return self.create(request, plan_id)


class NutrientEditView(PlanChildView):
    model, serializer_class, lookup = Nutrient, NutrientSerializer, "nutrient_id"

    @extend_schema(request=NutrientSerializer, responses={200: NutrientSerializer})
    def patch(self, request, plan_id, nutrient_id):
        return self.update(request, plan_id, nutrient_id=nutrient_id)

    @extend_schema(responses={204: None})
    def delete(self, request, plan_id, nutrient_id):
        return self.destroy(request, plan_id, nutrient_id=nutrient_id)


class SupplementEditView(PlanChildView):
    model, serializer_class, lookup = Supplement, SupplementSerializer, "supplement_id"

    @extend_schema(request=SupplementSerializer, responses={200: SupplementSerializer})
    def patch(self, request, plan_id, supplement_id):
        return self.update(request, plan_id, supplement_id=supplement_id)

    @extend_schema(responses={204: None})
    def delete(self, request, plan_id, supplement_id):
        return self.destroy(request, plan_id, supplement_id=supplement_id)
