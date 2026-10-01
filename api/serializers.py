from rest_framework import serializers


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class WeekTallySerializer(serializers.Serializer):
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    week_complete = serializers.BooleanField()


class CompletionSerializer(serializers.Serializer):
    completed = serializers.BooleanField()
    week_tally = WeekTallySerializer(required=False)


class MeUpdateSerializer(serializers.Serializer):
    timezone = serializers.CharField(max_length=64)

    def validate_timezone(self, value):
        from training.completions import is_valid_zone

        if not is_valid_zone(value):
            raise serializers.ValidationError("Must be an IANA time zone name, e.g. America/Chicago.")
        return value


class WorkoutTimingSerializer(serializers.Serializer):
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    ended_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        start, end = attrs.get("started_at"), attrs.get("ended_at")
        if start and end and end < start:
            raise serializers.ValidationError({"ended_at": ["Must not be before started_at."]})
        return attrs


SYNC_EVENT_TYPES = ["set_completed", "set_cleared", "workout_completed", "workout_cleared"]
MAX_SYNC_EVENTS = 500


class SyncEventSerializer(WorkoutTimingSerializer):
    """One queued change from the device. ``id`` is generated on the device
    and makes replays idempotent; ``occurred_at`` is when the user tapped and
    decides last-write-wins; ``log_date`` is the user's local calendar day."""

    id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=SYNC_EVENT_TYPES)
    log_date = serializers.DateField()
    occurred_at = serializers.DateTimeField()
    exercise_id = serializers.IntegerField(required=False)
    set_number = serializers.IntegerField(required=False, min_value=1)
    workout_id = serializers.IntegerField(required=False)
    week_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["type"].startswith("set_"):
            missing = [f for f in ("exercise_id", "set_number") if attrs.get(f) is None]
        else:
            missing = ["workout_id"] if attrs.get("workout_id") is None else []
            if attrs["type"] == "workout_completed" and attrs.get("week_id") is None:
                missing.append("week_id")
        if missing:
            raise serializers.ValidationError({f: ["This field is required for this event type."] for f in missing})
        return attrs


class SyncRequestSerializer(serializers.Serializer):
    # Items are validated one by one in the view so a single bad event is
    # rejected without failing the rest of the batch.
    events = serializers.ListField(child=serializers.DictField(), max_length=MAX_SYNC_EVENTS)


class SyncResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.ChoiceField(choices=["applied", "stale", "duplicate", "rejected"])
    errors = serializers.DictField(required=False)


class SyncResponseSerializer(serializers.Serializer):
    results = SyncResultSerializer(many=True)


# --- Response shapes for the client endpoints. The views build plain dicts;
# these describe them for the OpenAPI schema (and the generated app types),
# and api.tests checks the two stay in step. ---


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()
    roles = serializers.ListField(child=serializers.ChoiceField(choices=["owner", "trainer", "client"]))
    client_id = serializers.IntegerField(allow_null=True)
    trainer_id = serializers.IntegerField(allow_null=True)
    gym_id = serializers.IntegerField(allow_null=True)
    owned_gym_ids = serializers.ListField(child=serializers.IntegerField())
    timezone = serializers.CharField()
    today = serializers.DateField()


class ActiveAssignmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    client_id = serializers.IntegerField()
    assigned_at = serializers.DateTimeField()
    is_active = serializers.BooleanField()
    trainer_id = serializers.IntegerField()
    gym_id = serializers.IntegerField()


class ActivePlanSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    assignment = ActiveAssignmentSerializer()


class WorkoutSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    sub = serializers.CharField()
    flavor = serializers.CharField()
    color = serializers.CharField()
    order = serializers.IntegerField()


class ScheduleDaySerializer(serializers.Serializer):
    weekday = serializers.ChoiceField(choices=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    workout = WorkoutSummarySerializer(allow_null=True)


class ScheduleWeekSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    number = serializers.IntegerField()
    label = serializers.CharField()
    week_tally = WeekTallySerializer()
    days = ScheduleDaySerializer(many=True)


class SchedulePhaseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    note = serializers.CharField()
    order = serializers.IntegerField()
    number = serializers.IntegerField()
    weeks = ScheduleWeekSerializer(many=True)


class PlanRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()


class NoteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    amount = serializers.CharField()
    timing = serializers.CharField()
    notes = serializers.CharField()


class ScheduleSerializer(serializers.Serializer):
    date = serializers.DateField()
    plan = PlanRefSerializer()
    phases = SchedulePhaseSerializer(many=True)
    nutrients = NoteSerializer(many=True)
    supplements = NoteSerializer(many=True)


class ClientExerciseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    segment = serializers.ChoiceField(choices=["Main", "Core", "Cardio", "Stretch"])
    name = serializers.CharField()
    sets_count = serializers.IntegerField(allow_null=True)
    reps_text = serializers.CharField()
    rest_seconds = serializers.IntegerField(allow_null=True)
    time_text = serializers.CharField()
    order = serializers.IntegerField()
    completed_set_numbers = serializers.ListField(child=serializers.IntegerField())


class ClientWorkoutSerializer(WorkoutSummarySerializer):
    date = serializers.DateField()
    exercises = ClientExerciseSerializer(many=True)
    workout_completed = serializers.BooleanField()
    started_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)


class HistoryWorkoutSerializer(serializers.Serializer):
    date = serializers.DateField()
    workout = WorkoutSummarySerializer()
    week_id = serializers.IntegerField(allow_null=True)
    completed_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)


class HistorySerializer(serializers.Serializer):
    # "from" is a Python keyword, so the field is declared via the class dict.
    to = serializers.DateField()
    workouts = HistoryWorkoutSerializer(many=True)
    sets_completed_by_date = serializers.DictField(child=serializers.IntegerField())


HistorySerializer._declared_fields["from"] = serializers.DateField()
