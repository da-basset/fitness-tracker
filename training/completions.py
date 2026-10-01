"""Single write path for completion state (checked sets and finished
workouts), shared by the web toggles, the /api/v1/ PUT/DELETE endpoints and
the /api/v1/sync/ batch endpoint.

Every change is recorded as a SyncEvent so that conflicting changes to the
same set/workout/day resolve last-write-wins by ``occurred_at`` -- the time
the user tapped -- regardless of the order requests reach the server. That
is what lets an offline phone replay a queue hours later without undoing a
newer change made on the web in the meantime.
"""

import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CompletedSet, SyncEvent, WorkoutCompletion

APPLIED = SyncEvent.STATUS_APPLIED
STALE = SyncEvent.STATUS_STALE
DUPLICATE = "duplicate"

# How far past the user's own "today" a client-supplied log_date may be.
# One day absorbs devices whose clock/zone runs slightly ahead.
FUTURE_DATE_TOLERANCE = timedelta(days=1)


def user_zone(user):
    """The user's configured zone, falling back to the site default."""
    name = settings.TIME_ZONE
    profile = getattr(user, "profile", None) if user is not None else None
    if profile is not None and profile.timezone:
        name = profile.timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.TIME_ZONE)


def user_today(user):
    """The calendar date it currently is for this user."""
    return timezone.now().astimezone(user_zone(user)).date()


def is_valid_zone(name):
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def is_future_date(user, log_date):
    return log_date > user_today(user) + FUTURE_DATE_TOLERANCE


def set_target_key(exercise_id, set_number, log_date):
    return f"set:{exercise_id}:{set_number}:{log_date.isoformat()}"


def workout_target_key(workout_id, log_date):
    return f"workout:{workout_id}:{log_date.isoformat()}"


def _is_stale(client, target_key, occurred_at):
    latest = (
        SyncEvent.objects.filter(client=client, target_key=target_key, status=APPLIED)
        .order_by("-occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )
    return latest is not None and latest > occurred_at


def _record(client, event_id, event_type, target_key, occurred_at, apply):
    """Apply a change under last-write-wins and log it. Returns one of
    APPLIED, STALE or DUPLICATE."""
    event_id = event_id or uuid.uuid4()
    occurred_at = occurred_at or timezone.now()
    if SyncEvent.objects.filter(client=client, event_id=event_id).exists():
        return DUPLICATE
    try:
        with transaction.atomic():
            status = STALE if _is_stale(client, target_key, occurred_at) else APPLIED
            if status == APPLIED:
                apply()
            SyncEvent.objects.create(
                client=client,
                event_id=event_id,
                event_type=event_type,
                target_key=target_key,
                occurred_at=occurred_at,
                status=status,
            )
    except IntegrityError:
        # Same event_id raced in from a concurrent request.
        return DUPLICATE
    return status


def set_completion(client, exercise, set_number, log_date, completed, occurred_at=None, event_id=None):
    def apply():
        if completed:
            CompletedSet.objects.get_or_create(
                client=client, exercise=exercise, log_date=log_date, set_number=set_number
            )
        else:
            CompletedSet.objects.filter(
                client=client, exercise=exercise, log_date=log_date, set_number=set_number
            ).delete()

    return _record(
        client,
        event_id,
        "set_completed" if completed else "set_cleared",
        set_target_key(exercise.id, set_number, log_date),
        occurred_at,
        apply,
    )


def workout_completion(
    client,
    workout,
    log_date,
    completed,
    week=None,
    occurred_at=None,
    event_id=None,
    started_at=None,
    ended_at=None,
):
    def apply():
        if completed:
            row, created = WorkoutCompletion.objects.get_or_create(
                client=client,
                workout=workout,
                log_date=log_date,
                defaults={"week": week, "started_at": started_at, "ended_at": ended_at},
            )
            if not created and (started_at or ended_at):
                row.started_at = started_at or row.started_at
                row.ended_at = ended_at or row.ended_at
                row.save(update_fields=["started_at", "ended_at"])
        else:
            WorkoutCompletion.objects.filter(client=client, workout=workout, log_date=log_date).delete()

    return _record(
        client,
        event_id,
        "workout_completed" if completed else "workout_cleared",
        workout_target_key(workout.id, log_date),
        occurred_at,
        apply,
    )
