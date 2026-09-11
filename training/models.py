from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

MAX_PHASES = 6
MAX_WEEKS_PER_PHASE = 12

# A fixed palette of 7 colors to choose from for a workout's badge/day-cell
# color. Values are CSS class suffixes (see static/css/style.css's
# .badge-{color} / --train-{color} rules) -- not raw hex, so the palette
# stays themeable in one place.
COLOR_CHOICES = [
    ("red", "Red"),
    ("blue", "Blue"),
    ("green", "Green"),
    ("amber", "Amber"),
    ("violet", "Violet"),
    ("teal", "Teal"),
    ("rose", "Rose"),
]


class Plan(models.Model):
    """A trainer-owned workout plan: the parent for a set of Phases (and the
    Workouts referenced within them). A Trainer can build multiple Plans and
    assign the same Plan to more than one Client via PlanAssignment -- all
    assigned Clients share the same underlying Phase/Week/Workout data, so
    an edit to the plan is visible to everyone it's assigned to."""

    trainer = models.ForeignKey(
        "accounts.Trainer", on_delete=models.CASCADE, related_name="plans"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    # Set only on a per-client copy created by assigning a library template
    # (see training.services.clone_plan_for_client) -- null for the
    # template itself and for any plan created directly. A Plan's "kind" is
    # otherwise derived, not stored: zero PlanAssignments ever means a
    # reusable library template; being referenced by one means a client's
    # own independent copy, created once at assign-time and never shared.
    source_plan = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="clones"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return self.name

    def is_library_template(self):
        return not self.assignments.exists()


class PlanAssignment(models.Model):
    """Assigns a Plan to a Client. is_active marks the client's current
    plan; keeping past (inactive) rows around gives a simple assignment
    history without needing a separate audit table."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="assignments")
    client = models.ForeignKey(
        "accounts.Client", on_delete=models.CASCADE, related_name="plan_assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-assigned_at", "id"]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.plan} -> {self.client} ({status})"


class Workout(models.Model):
    """A workout type (e.g. Push, Pull, Legs & Stability), scoped to a
    single Plan. Fully editable -- name, description text, and color --
    and days-of-week assignments (WeekDay) just reference whichever
    Workouts currently exist within that plan."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="workouts")
    name = models.CharField(max_length=100)
    sub = models.CharField(max_length=150, blank=True, default="")
    flavor = models.CharField(max_length=250, blank=True, default="")
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default="red")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Exercise(models.Model):
    """One row in a workout's checklist table. Any exercise can be removed
    from its workout via the edit-mode delete button, regardless of origin.
    is_custom / created_by are kept only as a record of whether a row was
    seeded with the program or added later, and by whom."""

    SEGMENT_CHOICES = [
        ("Main", "Main"),
        ("Core", "Core"),
        ("Cardio", "Cardio"),
        ("Stretch", "Stretch"),
    ]

    workout = models.ForeignKey(Workout, related_name="exercises", on_delete=models.CASCADE)
    segment = models.CharField(max_length=10, choices=SEGMENT_CHOICES)
    name = models.CharField(max_length=200)

    # sets_count is null for rows that aren't "N sets of reps" (continuous
    # cardio, stretch blocks) -- those stay a single plain checkbox instead
    # of expanding into per-set checkboxes + a rest timer.
    sets_count = models.PositiveSmallIntegerField(null=True, blank=True)
    reps_text = models.CharField(max_length=60, blank=True, default="")
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    time_text = models.CharField(max_length=20, blank=True, default="")

    order = models.PositiveIntegerField(default=0)
    is_custom = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="added_exercises",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.workout.name}: {self.name}"

    def sets_reps_display(self):
        if self.sets_count:
            return f"{self.sets_count} x {self.reps_text}" if self.reps_text else f"{self.sets_count} x —"
        return self.reps_text or "—"

    def rest_display(self):
        if not self.rest_seconds:
            return "—"
        if self.rest_seconds % 60 == 0:
            return f"{self.rest_seconds // 60} min"
        return f"{self.rest_seconds} sec"

    def to_dict(self):
        return {
            "id": self.id,
            "segment": self.segment,
            "name": self.name,
            "sets_count": self.sets_count,
            "reps_text": self.reps_text,
            "rest_seconds": self.rest_seconds,
            "sets_reps_display": self.sets_reps_display(),
            "rest_display": self.rest_display(),
            "time_text": self.time_text,
            "is_custom": self.is_custom,
        }


class PlanNote(models.Model):
    """Abstract base for a trainer-authored reference-list row that hangs
    off a Plan and is shown read-only to clients -- shared shape for both
    Nutrient and Supplement (name + amount/dosage + optional timing +
    notes). Each concrete subclass just adds its own `plan` FK so the two
    lists stay separate (plan.nutrients vs plan.supplements) via Django's
    %(class)s related_name."""

    name = models.CharField(max_length=150)
    amount = models.CharField(
        max_length=100, blank=True, default="", help_text='e.g. "180g/day" or "5g"'
    )
    timing = models.CharField(
        max_length=100, blank=True, default="", help_text='e.g. "Morning" or "Post-workout"'
    )
    notes = models.TextField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Nutrient(PlanNote):
    """A single nutrition target on a plan's reference list, e.g. "Protein
    -- 180g/day". Read-only for the client; the trainer/owner manages the
    list from the plan's Workouts & Phases editor."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="nutrients")


class Supplement(PlanNote):
    """A single supplement recommendation on a plan's reference list, e.g.
    "Creatine -- 5g, morning". Read-only for the client; the trainer/owner
    manages the list from the plan's Workouts & Phases editor."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="supplements")


class Phase(models.Model):
    """A named block of a Plan (e.g. "Ramp-In", "Build", "Deload") made
    up of one or more Weeks. The app only caps the *number* of phases at
    MAX_PHASES; a phase's length is just however many Week children it has.
    Each Week is independently configurable -- its own Mon-Sun workout
    schedule -- so two weeks in the same phase can differ."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="phases")
    title = models.CharField(max_length=60, help_text='e.g. "Ramp-In", "Build", "Deload"')
    note = models.TextField(blank=True, default="", help_text="May include simple HTML like <strong>.")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def number(self):
        """1-indexed position of this phase among every phase *in the same
        plan*, in order -- used for the "Phase N" stamp so two phases
        sharing a title (e.g. two "Ramp-In" blocks) still read as distinct
        on the page. Scoped to plan so one trainer's plan never affects
        another trainer's phase numbering."""
        return 1 + Phase.objects.filter(plan=self.plan, order__lt=self.order).count()

    def week_range(self):
        """1-indexed (start, end) global week numbers spanned by this
        phase's weeks, based on every earlier phase's week count within
        the same plan."""
        weeks = list(self.weeks.all())
        if not weeks:
            start = 1 + Week.objects.filter(phase__plan=self.plan, phase__order__lt=self.order).count()
            return start, start
        return weeks[0].global_number(), weeks[-1].global_number()

    def label(self):
        start, end = self.week_range()
        return f"Week {start}" if start == end else f"Weeks {start}-{end}"

    def duration_weeks(self):
        return self.weeks.count()

    def sub(self):
        n = self.duration_weeks()
        return f"{n} week{'s' if n != 1 else ''}"

    def to_dict(self, client=None):
        return {
            "id": self.id,
            "title": self.title,
            "order": self.order,
            "number": self.number(),
            "note": self.note,
            "label": self.label(),
            "weeks": [week.to_dict(client=client) for week in self.weeks.all()],
        }


class Week(models.Model):
    """One week within a Phase, with its own independently configurable
    Mon-Sun workout schedule (WeekDay). Display strings like "Week 3" are
    computed from this week's position among every phase's weeks, not
    stored, so adding/removing/reordering weeks or phases keeps every
    week's displayed number correct automatically."""

    phase = models.ForeignKey(Phase, related_name="weeks", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.phase.title} — {self.label()}"

    def global_number(self):
        """1-indexed position of this week across the whole plan: every
        week in an earlier phase of the same plan, plus every earlier week
        in this phase."""
        earlier_phases = Week.objects.filter(
            phase__plan=self.phase.plan, phase__order__lt=self.phase.order
        ).count()
        earlier_in_phase = Week.objects.filter(phase=self.phase, order__lt=self.order).count()
        return earlier_phases + earlier_in_phase + 1

    def label(self):
        return f"Week {self.global_number()}"

    def stamp(self):
        return f"WK {self.global_number()}"

    def days_per_week(self):
        return self.days.exclude(workout=None).count()

    def week_tally(self, client):
        """How many of this week's workouts the given client has marked
        complete (via WorkoutCompletion) within the current Mon-Sun
        calendar week. Powers the tally badge and "week complete" stamp on
        the Physical Training page. Each workout tracks its own completed
        state independently (see WorkoutCompletion's docstring), so this
        is a straight count of completion rows -- marking two different
        workouts complete the same day legitimately counts as 2."""
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        completed = WorkoutCompletion.objects.filter(
            client=client, week=self, log_date__range=(week_start, week_end)
        ).count()
        total = self.days_per_week()
        return {
            "completed": completed,
            "total": total,
            "week_complete": total > 0 and completed >= total,
        }

    def sub(self):
        return f"{self.days_per_week()} days/week"

    def to_dict(self, client=None):
        data = {
            "id": self.id,
            "order": self.order,
            "label": self.label(),
            "stamp": self.stamp(),
            "sub": self.sub(),
            "days": {d.weekday: (d.workout_id if d.workout_id else None) for d in self.days.all()},
        }
        if client is not None:
            data["week_tally"] = self.week_tally(client)
        return data


class WeekDay(models.Model):
    """Which workout (if any) falls on a given weekday within a specific
    week. workout=None means a rest day."""

    WEEKDAYS = [
        ("Mon", "Mon"), ("Tue", "Tue"), ("Wed", "Wed"), ("Thu", "Thu"),
        ("Fri", "Fri"), ("Sat", "Sat"), ("Sun", "Sun"),
    ]

    week = models.ForeignKey(Week, related_name="days", on_delete=models.CASCADE)
    weekday = models.CharField(max_length=3, choices=WEEKDAYS)
    workout = models.ForeignKey(Workout, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ("week", "weekday")
        ordering = ["week_id", "id"]

    def __str__(self):
        return f"{self.week} {self.weekday}: {self.workout.name if self.workout else 'Rest'}"


class CompletedSet(models.Model):
    """One checked-off set, scoped to a client and a calendar day. Checking
    a set today persists across refreshes; a new day starts that
    exercise's checklist fresh again (and this table doubles as a simple
    history)."""

    client = models.ForeignKey("accounts.Client", on_delete=models.CASCADE, related_name="completed_sets")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="completions")
    log_date = models.DateField(default=timezone.localdate)
    set_number = models.PositiveSmallIntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("client", "exercise", "log_date", "set_number")

    def __str__(self):
        return f"{self.client} {self.exercise} set {self.set_number} on {self.log_date}"
class WorkoutCompletion(models.Model):
    """An explicit "I finished this workout today" flag, scoped to a user
    and a calendar day -- distinct from CompletedSet, which tracks
    individual checked-off sets. This is what the "Mark Completed" button
    and the weekly tally are built on, and it doubles as a durable
    consistency record: every row here is a completed workout day that a
    future history/consistency view can be built from.

    unique_together on (client, log_date, workout) means each workout
    tracks its own completed state for a given day independently --
    marking a second workout complete on the same day no longer un-marks
    the first one (that used to happen back when this was keyed on
    (user, log_date) alone, treating "today" as a single slot). week is
    recorded at completion time (whichever week tab was open) so the
    weekly tally stays correct even across a phase/week change mid-week."""

    client = models.ForeignKey(
        "accounts.Client", on_delete=models.CASCADE, related_name="workout_completions"
    )
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="completion_logs")
    week = models.ForeignKey(
        Week, null=True, blank=True, on_delete=models.SET_NULL, related_name="workout_completions"
    )
    log_date = models.DateField(default=timezone.localdate)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("client", "log_date", "workout")
        ordering = ["-log_date"]

    def __str__(self):
        return f"{self.client} completed {self.workout} on {self.log_date}"
