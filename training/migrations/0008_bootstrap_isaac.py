from django.db import migrations


def bootstrap_owner_trainer_client(apps, schema_editor):
    """One-time bootstrap: wrap whichever single User already exists (this
    app was single-user until now) into the first Gym/Trainer/Client, give
    them a Plan, and backfill every existing Phase/Workout row onto that
    Plan. A fresh install (no users yet) has nothing to backfill and is a
    no-op here -- seed_training creates the bootstrap itself in that case."""
    User = apps.get_model("auth", "User")
    Gym = apps.get_model("accounts", "Gym")
    Trainer = apps.get_model("accounts", "Trainer")
    Client = apps.get_model("accounts", "Client")
    Plan = apps.get_model("training", "Plan")
    Phase = apps.get_model("training", "Phase")
    Workout = apps.get_model("training", "Workout")

    users = list(User.objects.all())
    if not users:
        return
    if len(users) > 1:
        raise RuntimeError(
            "training.0008_bootstrap_isaac: expected exactly one existing "
            "user to bootstrap as the first Owner/Trainer/Client, found "
            f"{len(users)}. Resolve which user should own the existing "
            "Phase/Workout data manually before migrating."
        )
    user = users[0]

    gym, _ = Gym.objects.get_or_create(owner=user, defaults={"name": f"{user.username}'s Gym"})
    trainer, _ = Trainer.objects.get_or_create(user=user, defaults={"gym": gym})
    Client.objects.get_or_create(user=user, defaults={"trainer": trainer})
    plan, _ = Plan.objects.get_or_create(
        trainer=trainer, name=f"{user.username}'s Plan", defaults={"description": ""}
    )

    Phase.objects.filter(plan__isnull=True).update(plan=plan)
    Workout.objects.filter(plan__isnull=True).update(plan=plan)


def unbootstrap_owner_trainer_client(apps, schema_editor):
    """Reversal: null out the backfilled plan FKs and remove the bootstrap
    rows this migration created. Not a full inverse if you've since created
    more Gyms/Trainers/Clients/Plans by hand -- reverse this migration on a
    live system with care."""
    Phase = apps.get_model("training", "Phase")
    Workout = apps.get_model("training", "Workout")
    Plan = apps.get_model("training", "Plan")
    Client = apps.get_model("accounts", "Client")
    Trainer = apps.get_model("accounts", "Trainer")
    Gym = apps.get_model("accounts", "Gym")

    Phase.objects.all().update(plan=None)
    Workout.objects.all().update(plan=None)
    Plan.objects.all().delete()
    Client.objects.all().delete()
    Trainer.objects.all().delete()
    Gym.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0007_plan_phase_plan_workout_plan_planassignment"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(bootstrap_owner_trainer_client, unbootstrap_owner_trainer_client),
    ]
