from django.db import migrations


def backfill_client_and_assignments(apps, schema_editor):
    """Step 2 of 3: populate the new `client` FK on every existing
    CompletedSet/WorkoutCompletion row from its (still-present) `user` FK,
    via that user's Client profile. Also closes a gap left by the phase-1
    migration (training.0008_bootstrap_isaac): it created a Gym/Trainer/
    Client/Plan for the app's existing user and backfilled Phase/Workout
    onto that Plan, but never created the PlanAssignment linking the
    Client to the Plan -- so every existing Client gets one here (their
    trainer's first Plan), skipping any Client that already has one."""
    Client = apps.get_model("accounts", "Client")
    Plan = apps.get_model("training", "Plan")
    PlanAssignment = apps.get_model("training", "PlanAssignment")
    CompletedSet = apps.get_model("training", "CompletedSet")
    WorkoutCompletion = apps.get_model("training", "WorkoutCompletion")

    client_by_user_id = {c.user_id: c for c in Client.objects.all()}

    for row in CompletedSet.objects.filter(client__isnull=True):
        client = client_by_user_id.get(row.user_id)
        if client is not None:
            row.client = client
            row.save(update_fields=["client"])

    for row in WorkoutCompletion.objects.filter(client__isnull=True):
        client = client_by_user_id.get(row.user_id)
        if client is not None:
            row.client = client
            row.save(update_fields=["client"])

    for client in Client.objects.all():
        if PlanAssignment.objects.filter(client=client, is_active=True).exists():
            continue
        plan = Plan.objects.filter(trainer=client.trainer).order_by("id").first()
        if plan is not None:
            PlanAssignment.objects.create(plan=plan, client=client, is_active=True)


def unbackfill_client_and_assignments(apps, schema_editor):
    """Reversal: null out the client FKs this migration populated. Doesn't
    delete the PlanAssignment rows it created since those may have been
    relied on since (e.g. re-assigned) -- treat reversing this on a live
    system with care, same as 0008's reversal."""
    CompletedSet = apps.get_model("training", "CompletedSet")
    WorkoutCompletion = apps.get_model("training", "WorkoutCompletion")
    CompletedSet.objects.all().update(client=None)
    WorkoutCompletion.objects.all().update(client=None)


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0010_completedset_client_workoutcompletion_client"),
    ]

    operations = [
        migrations.RunPython(backfill_client_and_assignments, unbackfill_client_and_assignments),
    ]
