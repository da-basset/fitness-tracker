from accounts.models import Client, Gym, Trainer
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from training.models import Exercise, Phase, Plan, PlanAssignment, Week, WeekDay, Workout

# Keyed by a short internal label used only within this script (to wire up
# WeekDay assignments below) -- not stored anywhere on the model anymore.
WORKOUTS = {
    "A": {
        "name": "Push", "sub": "Chest, Shoulders, Triceps + Posture", "color": "red",
        "flavor": "Weeks 1-4: use 2 sets per main exercise instead of 3.",
        "rows": [
            ("Main", "Barbell Bench Press", 3, "8-10", 90, "~7 min"),
            ("Main", "Seated DB Shoulder Press", 3, "10", 75, "~6 min"),
            ("Main", "Incline DB Press (bench @ 30-45°)", 3, "10", 75, "~6 min"),
            ("Main", "Cable Face Pulls (posture)", 3, "15", 60, "~5 min"),
            ("Main", "EZ Bar Overhead Triceps Extension", 3, "12", 60, "~5 min"),
            ("Main", "Cable Triceps Pushdown", 2, "15", 45, "~4 min"),
            ("Main", "Push-up Finisher (bodyweight)", 2, "AMRAP", 60, "~3 min"),
            ("Core", "Ab Wheel Rollout", 3, "8-10", 30, "~3 min"),
            ("Core", "Plank", 2, "45 sec", 30, "~2 min"),
            ("Cardio", "Jump Rope Intervals", 5, "45 sec", 15, "5 min"),
            ("Stretch", "Doorway Chest, OH Triceps, Child's Pose, Cat-Cow", None, "—", None, "5 min"),
        ],
    },
    "B": {
        "name": "Pull", "sub": "Back, Biceps, Forearms + Posture", "color": "blue",
        "flavor": "Weeks 3-4: use 2-3 sets per main exercise. Weeks 5+: full 3 sets.",
        "rows": [
            ("Main", "Deadlift (light to build back up)", 3, "5", 120, "~9 min"),
            ("Main", "Lat Pulldown (wide grip)", 3, "10", 75, "~6 min"),
            ("Main", "Seated Cable Row (squeeze shoulder blades)", 3, "12", 75, "~6 min"),
            ("Main", "Single-Arm DB Row", 3, "10/side", 60, "~6 min"),
            ("Main", "EZ Bar Curl", 3, "10", 60, "~5 min"),
            ("Main", "Preacher Curl", 2, "12", 60, "~4 min"),
            ("Main", "DB Wrist Curl / Reverse Curl", 2, "15", 45, "~3 min"),
            ("Core", "Trunk Rotation (standing DB twist / woodchop)", 3, "12/side", 30, "~3 min"),
            ("Core", "Supermans", 2, "12", 30, "~2 min"),
            ("Cardio", "Treadmill Incline Walk / Jog Intervals", 5, "45 sec", 15, "5 min"),
            ("Stretch", "Lat, Forearm, Thoracic Rotation, Cat-Cow", None, "—", None, "5 min"),
        ],
    },
    "C": {
        "name": "Legs & Stability", "sub": "Knee / Ankle Focus", "color": "green",
        "flavor": "Weeks 1-4: use 2 sets per main exercise instead of 3.",
        "rows": [
            ("Main", "Back Squat (light, controlled depth)", 3, "8", 90, "~7 min"),
            ("Main", "Romanian Deadlift (DB or barbell)", 3, "10", 90, "~7 min"),
            ("Main", "Bulgarian Split Squat (rear foot on bench)", 3, "8/leg", 75, "~7 min"),
            ("Main", "Step-Ups (lowest plyo box height)", 3, "10/leg", 60, "~6 min"),
            ("Main", "Standing Calf Raise", 3, "15", 45, "~4 min"),
            ("Main", "Single-Leg Balance Reach", 2, "10/leg", 45, "~3 min"),
            ("Main", "Wall Sit", 2, "30-45 sec", 45, "~3 min"),
            ("Core", "Trunk Rotation (seated or standing)", 3, "12/side", 30, "~3 min"),
            ("Core", "Ab Wheel Rollout", 2, "8", 30, "~2 min"),
            ("Cardio", "Treadmill Light Jog/Walk (low-impact)", None, "5 min cont.", None, "5 min"),
            ("Stretch", "Hip Flexor, Hamstring, Quad, Calf, Figure-4", None, "—", None, "5 min"),
        ],
    },
    "D": {
        "name": "Full Body Power", "sub": "Kettlebell / Jump Rope / Jumping", "color": "amber",
        "flavor": "Only appears from Week 5 onward. No kettlebell? Sub a heavy dumbbell held goblet-style.",
        "rows": [
            ("Main", "Kettlebell Goblet Squat", 3, "12", 60, "~6 min"),
            ("Main", "Kettlebell Swings", 3, "15", 60, "~6 min"),
            ("Main", "Box Jumps (lowest height, soft landing)", 3, "8", 75, "~6 min"),
            ("Main", "DB Push Press", 3, "8", 75, "~6 min"),
            ("Main", "Renegade Rows (DB, plank position)", 3, "10/side", 60, "~7 min"),
            ("Main", "Jump Rope Circuit", 4, "60 sec", 30, "~6 min"),
            ("Core", "Plank to Ab Wheel Combo", 3, "8 rollouts", 30, "~3 min"),
            ("Core", "Trunk Rotation", 2, "12/side", 30, "~2 min"),
            ("Cardio", "Jump Rope Sprint Intervals", 5, "30 sec", 30, "5 min"),
            ("Stretch", "Hamstring, Quad, Chest, Shoulder, Calf Flow", None, "—", None, "5 min"),
        ],
    },
    "E": {
        "name": "Upper Accessory", "sub": "Posture & Mobility Focus", "color": "violet",
        "flavor": "Weeks 1-2: use 2 sets per main exercise instead of 3.",
        "rows": [
            ("Main", "Chin-Ups", 3, "8-10", 90, "~6 min"),
            ("Main", "Pull-Ups", 3, "6-8", 90, "~6 min"),
            ("Main", "DB Lateral Raise", 3, "12", 60, "~5 min"),
            ("Main", "Rear Delt Fly (posture)", 3, "15", 60, "~5 min"),
            ("Main", "Hammer Curl", 3, "12", 60, "~5 min"),
            ("Main", "Bench Dips (triceps)", 3, "10", 60, "~5 min"),
            ("Main", "Wrist / Reverse Curl", 2, "15", 45, "~3 min"),
            ("Core", "Supermans", 2, "12", 30, "~2 min"),
            ("Core", "Ab Wheel Rollout", 2, "8-10", 30, "~3 min"),
            ("Cardio", "Jump Rope or Treadmill Intervals", 5, "45 sec", 15, "5 min"),
            ("Stretch", "Chest Opener, Thoracic Ext., Neck, Doorway", None, "—", None, "5 min"),
        ],
    },
}

FULL_WEEK = {"Mon": "A", "Tue": "B", "Wed": "C", "Thu": None, "Fri": "D", "Sat": "E", "Sun": None}

PHASES = [
    {
        "title": "Ramp-In", "duration_weeks": 2,
        "days": {"Mon": "A", "Tue": None, "Wed": "C", "Thu": None, "Fri": "E", "Sat": None, "Sun": None},
        "note": ("<strong>Goal:</strong> reintroduce your body to consistent training. "
                 "Use lighter weight than your old numbers -- form and joint comfort over load. "
                 "2 sets per main exercise."),
    },
    {
        "title": "Ramp-In", "duration_weeks": 2,
        "days": {"Mon": "A", "Tue": "B", "Wed": None, "Thu": "C", "Fri": None, "Sat": "E", "Sun": None},
        "note": ("Pull day is back in. Legs still has a rest day on both sides -- "
                 "no back-to-back knee loading yet. 2-3 sets per main exercise."),
    },
    {
        "title": "Build", "duration_weeks": 4,
        "days": FULL_WEEK,
        "note": ("Full plan, re-sequenced: Legs (Wed) and Full Body/box jumps (Fri) are now "
                 "split by a rest day instead of stacked. 3 sets per main exercise."),
    },
    {
        "title": "Deload", "duration_weeks": 1,
        "days": FULL_WEEK,
        "note": ("Same schedule as the Build phase, but drop to <strong>2 sets</strong> and cut weight "
                 "<strong>~40-50%</strong> on every exercise below. Core/cardio/stretch stay normal. "
                 "On Full Body day, skip or halve the box jump volume."),
    },
    {
        "title": "Build 2", "duration_weeks": 3,
        "days": FULL_WEEK,
        "note": ("Same schedule as the Build phase. You're coming off a deload with weeks behind you -- "
                 "push weight/reps a bit harder than before, as long as joints feel good. "
                 "Re-test push-ups/chin-ups/pull-ups at the end."),
    },
]


class Command(BaseCommand):
    help = (
        "Seed the built-in workouts, exercises, and phase schedule into a Plan "
        "(first-run only per workout). Bootstraps the target user as an "
        "Owner/Trainer/Client if they aren't one yet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            help=(
                "Username to bootstrap as Owner/Trainer/Client and seed a Plan for. "
                "Defaults to the only existing superuser, if there's exactly one."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = options.get("username")
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f'No user named "{username}". Create one first (e.g. createsuperuser).')
        else:
            superusers = list(User.objects.filter(is_superuser=True))
            if len(superusers) != 1:
                raise CommandError(
                    "Pass --username explicitly: found %d superusers (need exactly 1 to infer one)."
                    % len(superusers)
                )
            user = superusers[0]

        gym, _ = Gym.objects.get_or_create(owner=user, defaults={"name": f"{user.username}'s Gym"})
        trainer, _ = Trainer.objects.get_or_create(user=user, defaults={"gym": gym})
        client, _ = Client.objects.get_or_create(user=user, defaults={"trainer": trainer})
        plan, _ = Plan.objects.get_or_create(
            trainer=trainer, name=f"{user.username}'s Plan", defaults={"description": ""}
        )
        if not PlanAssignment.objects.filter(client=client, is_active=True).exists():
            PlanAssignment.objects.create(plan=plan, client=client, is_active=True)

        workout_objs = {}
        for order, (key, data) in enumerate(WORKOUTS.items(), start=1):
            workout, created = Workout.objects.get_or_create(
                plan=plan,
                name=data["name"],
                defaults={"sub": data["sub"], "flavor": data["flavor"], "color": data["color"], "order": order},
            )
            workout_objs[key] = workout

            # Only populate exercises the very first time this workout is
            # seeded. If you've since removed or added rows through the
            # editor, re-running this command won't undo that.
            if not workout.exercises.exists():
                for row_order, (segment, name, sets_count, reps_text, rest_seconds, time_text) in enumerate(data["rows"]):
                    Exercise.objects.create(
                        workout=workout,
                        segment=segment,
                        name=name,
                        sets_count=sets_count,
                        reps_text=reps_text,
                        rest_seconds=rest_seconds,
                        time_text=time_text,
                        order=row_order,
                        is_custom=False,
                    )
                self.stdout.write(self.style.SUCCESS(f"Seeded exercises for {data['name']}"))
            else:
                self.stdout.write(f"{data['name']} already has exercises -- left as-is")

        if Phase.objects.filter(plan=plan).exists():
            self.stdout.write("Phases already exist for this plan -- leaving schedule as-is")
            self.stdout.write(self.style.SUCCESS("Done."))
            return

        for order, phase_data in enumerate(PHASES, start=1):
            phase = Phase.objects.create(
                plan=plan,
                title=phase_data["title"],
                note=phase_data["note"],
                order=order,
            )
            for week_order in range(1, phase_data["duration_weeks"] + 1):
                week = Week.objects.create(phase=phase, order=week_order)
                for weekday, key in phase_data["days"].items():
                    WeekDay.objects.create(
                        week=week,
                        weekday=weekday,
                        workout=workout_objs[key] if key else None,
                    )
            self.stdout.write(self.style.SUCCESS(f"Seeded phase {phase.title} ({phase.duration_weeks()}w)"))

        self.stdout.write(self.style.SUCCESS("Done."))
