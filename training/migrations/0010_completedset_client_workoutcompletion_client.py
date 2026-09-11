# Step 1 of 3 for swapping CompletedSet/WorkoutCompletion from `user` to
# `client`: add the new FK nullable first so 0011's data migration can
# backfill it from the still-present `user` column before anything is
# removed or locked down.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('training', '0009_alter_phase_plan_alter_workout_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='completedset',
            name='client',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='completed_sets', to='accounts.client'),
        ),
        migrations.AddField(
            model_name='workoutcompletion',
            name='client',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workout_completions', to='accounts.client'),
        ),
    ]
