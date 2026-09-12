from accounts.models import Client, Gym, Trainer
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from training.models import Exercise, Phase, Plan, PlanAssignment, Week, WeekDay, Workout

# username -> password. Kept simple/memorable since these are local demo
# accounts for Isaac to log in as and poke around the UI with -- not
# meant to be production credentials.
DEMO_ACCOUNTS = {
    "owner": {"username": "Owner1", "password": "Owner1pass"},
    "trainer": {"username": "Trainer1", "password": "Trainer1pass"},
    "client": {"username": "Client1", "password": "Client1pass"},
}

# A small two-workout sample plan -- enough to see phases, weeks, a
# workout schedule, and a real exercise checklist without being as large
# as seed_training's full 5-workout program.
WORKOUTS = {
    "A": {
        "name": "Push Day", "sub": "Chest, Shoulders, Triceps", "color": "red",
        "flavor": "Sample plan -- swap in your own exercises any time from the edit view.",
        "rows": [
            ("Main", "Barbell Bench Press", 3, "8-10", 90, "~7 min"),
            ("Main", "Seated DB Shoulder Press", 3, "10", 75, "~6 min"),
            ("Main", "Cable Triceps Pushdown", 3, "12", 60, "~5 min"),
            ("Core", "Plank", 3, "45 sec", 30, "~3 min"),
            ("Cardio", "Jump Rope Intervals", 5, "45 sec", 15, "5 min"),
            ("Stretch", "Doorway Chest Stretch + Child's Pose", None, "—", None, "5 min"),
        ],
    },
    "B": {
        "name": "Legs Day", "sub": "Quads, Hamstrings, Glutes", "color": "green",
        "flavor": "Sample plan -- swap in your own exercises any time from the edit view.",
        "rows": [
            ("Main", "Back Squat", 3, "8", 90, "~7 min"),
            ("Main", "Romanian Deadlift", 3, "10", 90, "~7 min"),
            ("Main", "Walking Lunges", 3, "10/leg", 60, "~6 min"),
            ("Core", "Ab Wheel Rollout", 3, "8-10", 30, "~3 min"),
            ("Cardio", "Treadmill Incline Walk", None, "5 min cont.", None, "5 min"),
            ("Stretch", "Hip Flexor + Hamstring Stretch", None, "—", None, "5 min"),
        ],
    },
}

PHASES = [
    {
        "title": "Foundations", "duration_weeks": 2,
        "days": {"Mon": "A", "Tue": None, "Wed": "B", "Thu": None, "Fri": "A", "Sat": None, "Sun": None},
        "note": "<strong>Goal:</strong> build a consistent 3-day/week habit before adding volume.",
    },
    {
        "title": "Build", "duration_weeks": 2,
        "days": {"Mon": "A", "Tue": "B", "Wed": None, "Thu": "A", "Fri": "B", "Sat": None, "Sun": None},
        "note": "Bumped to 4 days/week. Increase weight on main lifts once every set feels solid.",
    },
]


class Command(BaseCommand):
    help = (
        "Create demo Owner1/Trainer1/Client1 accounts (Owner1's Gym -> Trainer1 -> "
        "Client1), assign Client1 a sample two-phase plan, and seed it with workouts "
        "and exercises. Safe to re-run -- existing users/profiles/data are left as-is "
        "and only missing pieces are filled in."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        created_users = {}

        for key, info in DEMO_ACCOUNTS.items():
            user, created = User.objects.get_or_create(username=info["username"])
            if created:
                user.set_password(info["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user {info['username']} (password: {info['password']})"))
            else:
                self.stdout.write(f"User {info['username']} already exists -- leaving password as-is")
            created_users[key] = user

        owner_user = created_users["owner"]
        trainer_user = created_users["trainer"]
        client_user = created_users["client"]

        gym, gym_created = Gym.objects.get_or_create(
            owner=owner_user, defaults={"name": f"{owner_user.username}'s Gym"}
        )
        if gym_created:
            self.stdout.write(self.style.SUCCESS(f"Created gym: {gym.name}"))

        trainer, trainer_created = Trainer.objects.get_or_create(
            user=trainer_user, defaults={"gym": gym}
        )
        if trainer_created:
            self.stdout.write(self.style.SUCCESS(f"Created trainer profile for {trainer_user.username}"))

        client, client_created = Client.objects.get_or_create(
            user=client_user, defaults={"trainer": trainer}
        )
        if client_created:
            self.stdout.write(self.style.SUCCESS(f"Created client profile for {client_user.username} (trainer: {trainer_user.username})"))

        plan, plan_created = Plan.objects.get_or_create(
            trainer=trainer, name="Sample Plan",
            defaults={"description": "A sample two-phase plan for reviewing the client experience."},
        )
        if plan_created:
            self.stdout.write(self.style.SUCCESS(f"Created plan: {plan.name}"))

        PlanAssignment.objects.filter(client=client, is_active=True).exclude(plan=plan).update(is_active=False)
        _, assignment_created = PlanAssignment.objects.update_or_create(
            plan=plan, client=client, defaults={"is_active": True}
        )
        if assignment_created:
            self.stdout.write(self.style.SUCCESS(f"Assigned {plan.name} to {client_user.username}"))

        workout_objs = {}
        for order, (key, data) in enumerate(WORKOUTS.items(), start=1):
            workout, created = Workout.objects.get_or_create(
                plan=plan, name=data["name"],
                defaults={"sub": data["sub"], "flavor": data["flavor"], "color": data["color"], "order": order},
            )
            workout_objs[key] = workout
            if not workout.exercises.exists():
                for row_order, (segment, name, sets_count, reps_text, rest_seconds, time_text) in enumerate(data["rows"]):
                    Exercise.objects.create(
                        workout=workout, segment=segment, name=name, sets_count=sets_count,
                        reps_text=reps_text, rest_seconds=rest_seconds, time_text=time_text,
                        order=row_order, is_custom=False,
                    )
                self.stdout.write(self.style.SUCCESS(f"Seeded exercises for {data['name']}"))
            else:
                self.stdout.write(f"{data['name']} already has exercises -- left as-is")

        if Phase.objects.filter(plan=plan).exists():
            self.stdout.write("Phases already exist for this plan -- leaving schedule as-is")
        else:
            for order, phase_data in enumerate(PHASES, start=1):
                phase = Phase.objects.create(
                    plan=plan, title=phase_data["title"], note=phase_data["note"], order=order,
                )
                for week_order in range(1, phase_data["duration_weeks"] + 1):
                    week = Week.objects.create(phase=phase, order=week_order)
                    for weekday, key in phase_data["days"].items():
                        WeekDay.objects.create(
                            week=week, weekday=weekday,
                            workout=workout_objs[key] if key else None,
                        )
                self.stdout.write(self.style.SUCCESS(f"Seeded phase {phase.title} ({phase.duration_weeks()}w)"))

        self.stdout.write(self.style.SUCCESS("Done."))
        self.stdout.write("")
        self.stdout.write("Login credentials (new accounts only -- unchanged if they already existed):")
        for info in DEMO_ACCOUNTS.values():
            self.stdout.write(f"  {info['username']} / {info['password']}")
