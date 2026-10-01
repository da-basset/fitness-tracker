"""Serializers for the trainer/owner management API (``api.manage``)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.forms import AccountCreateForm
from training.models import Exercise, Nutrient, Phase, Supplement, WeekDay, Workout

WEEKDAY_NAMES = [name for name, _ in WeekDay.WEEKDAYS]


def display_name(user):
    return user.get_full_name() or user.username


class AccountCreateSerializer(serializers.Serializer):
    """New login for a Trainer or Client. Validation is the web form's
    (username uniqueness, Django's password validators), so both surfaces
    accept and reject the same accounts."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        form = AccountCreateForm(
            data={
                "username": attrs["username"],
                "first_name": attrs["first_name"],
                "last_name": attrs["last_name"],
                "email": attrs["email"],
                "password1": attrs["password"],
                "password2": attrs["password"],
            }
        )
        if not form.is_valid():
            errors = dict(form.errors)
            errors["password"] = errors.pop("password2", []) + errors.pop("password1", [])
            raise serializers.ValidationError({key: list(value) for key, value in errors.items() if value})
        attrs["form"] = form
        return attrs

    def create(self, validated_data):
        return validated_data["form"].save()


class PersonSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    email = serializers.CharField(source="user.email")
    name = serializers.SerializerMethodField()

    def get_name(self, obj) -> str:
        return display_name(obj.user)


class TrainerSerializer(PersonSerializer):
    id = serializers.IntegerField()
    gym_id = serializers.IntegerField()
    client_count = serializers.SerializerMethodField()

    def get_client_count(self, obj) -> int:
        return obj.clients.count()


class ActivePlanRefSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField()
    plan_id = serializers.IntegerField()
    plan_name = serializers.CharField()
    assigned_at = serializers.DateTimeField()


class ClientSummarySerializer(PersonSerializer):
    id = serializers.IntegerField()
    trainer_id = serializers.IntegerField()
    trainer_name = serializers.SerializerMethodField()
    active_plan = serializers.SerializerMethodField()

    def get_trainer_name(self, obj) -> str:
        return display_name(obj.trainer.user)

    @extend_schema_field(ActivePlanRefSerializer(allow_null=True))
    def get_active_plan(self, obj):
        assignment = next((a for a in obj.plan_assignments.all() if a.is_active), None)
        if assignment is None:
            return None
        return {
            "assignment_id": assignment.id,
            "plan_id": assignment.plan_id,
            "plan_name": assignment.plan.name,
            "assigned_at": assignment.assigned_at,
        }


class PlanSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    trainer_id = serializers.IntegerField(read_only=True)
    source_plan_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class AssignmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    plan_id = serializers.IntegerField()
    plan_name = serializers.CharField(source="plan.name")
    client_id = serializers.IntegerField()
    assigned_at = serializers.DateTimeField()
    is_active = serializers.BooleanField()


class ClientStatsSerializer(serializers.Serializer):
    all_time_completed = serializers.IntegerField()
    last_completed_at = serializers.DateField(allow_null=True)


class ClientDetailSerializer(ClientSummarySerializer):
    active_assignment = AssignmentSerializer(allow_null=True)
    past_assignments = AssignmentSerializer(many=True)
    stats = ClientStatsSerializer(allow_null=True)
    templates = PlanSummarySerializer(many=True)


class AssignRequestSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()


class ReorderRequestSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class WorkoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workout
        fields = ["id", "name", "sub", "flavor", "color", "order"]
        read_only_fields = ["id"]
        extra_kwargs = {"order": {"required": False}}


class ExerciseSerializer(serializers.ModelSerializer):
    """Same limits as the web editor's _validate_exercise_payload."""

    sets_count = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=20)
    rest_seconds = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=3600)

    class Meta:
        model = Exercise
        fields = [
            "id", "workout_id", "segment", "name", "sets_count", "reps_text",
            "rest_seconds", "time_text", "order", "is_custom",
        ]
        read_only_fields = ["id", "workout_id", "order", "is_custom"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Exercise name is required.")
        return value


class WorkoutDetailSerializer(WorkoutSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)

    class Meta(WorkoutSerializer.Meta):
        fields = WorkoutSerializer.Meta.fields + ["exercises"]


class WeekSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    number = serializers.IntegerField(source="global_number")
    label = serializers.CharField()
    days = serializers.SerializerMethodField()

    def get_days(self, obj) -> dict[str, int | None]:
        assigned = {day.weekday: day.workout_id for day in obj.days.all()}
        return {name: assigned.get(name) for name in WEEKDAY_NAMES}


class WeekDaysSerializer(serializers.Serializer):
    """A week's Mon-Sun schedule: weekday -> workout id, or null for rest.
    Weekdays left out keep their current value."""

    days = serializers.DictField(child=serializers.IntegerField(allow_null=True))

    def validate_days(self, value):
        unknown = sorted(set(value) - set(WEEKDAY_NAMES))
        if unknown:
            raise serializers.ValidationError(f"Unknown weekday(s): {', '.join(unknown)}.")
        plan = self.context["plan"]
        valid = set(plan.workouts.values_list("id", flat=True))
        foreign = sorted({wid for wid in value.values() if wid is not None and wid not in valid})
        if foreign:
            raise serializers.ValidationError(f"Workout(s) not in this plan: {foreign}.")
        return value


class PhaseSerializer(serializers.ModelSerializer):
    number = serializers.IntegerField(read_only=True)
    weeks = WeekSerializer(many=True, read_only=True)

    class Meta:
        model = Phase
        fields = ["id", "title", "note", "order", "number", "weeks"]
        read_only_fields = ["id"]
        extra_kwargs = {"order": {"required": False}}


class NutrientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nutrient
        fields = ["id", "name", "amount", "timing", "notes", "order"]
        read_only_fields = ["id"]
        extra_kwargs = {"order": {"required": False}}


class SupplementSerializer(NutrientSerializer):
    class Meta(NutrientSerializer.Meta):
        model = Supplement


class OwningClientSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PlanLimitsSerializer(serializers.Serializer):
    max_phases = serializers.IntegerField()
    max_weeks_per_phase = serializers.IntegerField()


class PlanDetailSerializer(PlanSummarySerializer):
    """Everything an editor, preview or past-plan view needs in one read."""

    is_template = serializers.BooleanField()
    can_manage = serializers.BooleanField()
    owning_client = OwningClientSerializer(allow_null=True)
    assignment = AssignmentSerializer(allow_null=True)
    workouts = WorkoutDetailSerializer(many=True)
    phases = PhaseSerializer(many=True)
    nutrients = NutrientSerializer(many=True)
    supplements = SupplementSerializer(many=True)
    limits = PlanLimitsSerializer()
