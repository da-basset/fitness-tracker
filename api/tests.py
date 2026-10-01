from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Client, Gym, Trainer
from training.models import Exercise, Phase, Plan, PlanAssignment, Week, WeekDay, Workout

User = get_user_model()


class NativeApiTestCase(TestCase):
    """Shared fixtures: one gym, owner, trainer, client and an assigned plan."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pw")
        self.gym = Gym.objects.create(name="Gym", owner=self.owner)
        self.trainer_user = User.objects.create_user("trainer", password="pw")
        self.trainer = Trainer.objects.create(user=self.trainer_user, gym=self.gym)
        self.user = User.objects.create_user("client", password="pw")
        self.client_profile = Client.objects.create(user=self.user, trainer=self.trainer)
        self.plan = Plan.objects.create(trainer=self.trainer, name="Native plan")
        self.workout = Workout.objects.create(plan=self.plan, name="Push", order=1)
        self.exercise = Exercise.objects.create(
            workout=self.workout, segment="Main", name="Bench", sets_count=3, order=1
        )
        self.cardio = Exercise.objects.create(workout=self.workout, segment="Cardio", name="Walk", order=2)
        self.phase = Phase.objects.create(plan=self.plan, title="Block", order=1)
        self.week = Week.objects.create(phase=self.phase, order=1)
        WeekDay.objects.create(week=self.week, weekday="Mon", workout=self.workout)
        self.assignment = PlanAssignment.objects.create(plan=self.plan, client=self.client_profile, is_active=True)

    def token_pair(self, username="client", password="pw"):
        response = self.client.post(
            reverse("api_token_obtain_pair"),
            {"username": username, "password": password},
            content_type="application/json",
        )
        return response

    def auth(self):
        response = self.token_pair()
        self.assertEqual(response.status_code, 200)
        return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['access']}"}

    def auth_for(self, username):
        response = self.token_pair(username)
        self.assertEqual(response.status_code, 200)
        return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['access']}"}


class NativeApiTests(NativeApiTestCase):
    def test_tokens_rotate_blacklist_and_logout(self):
        pair = self.token_pair()
        self.assertEqual(pair.status_code, 200)
        refresh = pair.json()["refresh"]
        rotated = self.client.post(
            reverse("api_token_refresh"), {"refresh": refresh}, content_type="application/json"
        )
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(refresh, rotated.json()["refresh"])
        self.assertEqual(
            self.client.post(
                reverse("api_token_refresh"), {"refresh": refresh}, content_type="application/json"
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                reverse("api_logout"),
                {"refresh": rotated.json()["refresh"]},
                content_type="application/json",
                **self.auth(),
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.post(
                reverse("api_token_refresh"), {"refresh": rotated.json()["refresh"]}, content_type="application/json"
            ).status_code,
            401,
        )
        self.assertEqual(self.token_pair(password="wrong").status_code, 401)

    def test_me_reports_all_roles(self):
        # A user may legitimately have owner, trainer, and client identities.
        trainer = Trainer.objects.create(user=self.owner, gym=self.gym)
        owner_client = Client.objects.create(user=self.owner, trainer=trainer)
        response = self.client.get(reverse("api_me"), **self.auth_for("owner"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["owner", "trainer", "client"])
        self.assertEqual(response.json()["client_id"], owner_client.id)

    def test_schedule_and_workout_are_client_scoped(self):
        schedule = self.client.get(reverse("api_active_schedule"), **self.auth())
        self.assertEqual(schedule.status_code, 200)
        self.assertEqual(schedule.json()["phases"][0]["weeks"][0]["days"][0]["weekday"], "Mon")
        workout = self.client.get(reverse("api_workout", args=[self.workout.id]), **self.auth())
        self.assertEqual(workout.status_code, 200)
        self.assertEqual(workout.json()["exercises"][0]["completed_set_numbers"], [])

        other_user = User.objects.create_user("other", password="pw")
        other = Client.objects.create(user=other_user, trainer=self.trainer)
        other_plan = Plan.objects.create(trainer=self.trainer, name="Other")
        PlanAssignment.objects.create(plan=other_plan, client=other, is_active=True)
        self.assertEqual(
            self.client.get(reverse("api_workout", args=[self.workout.id]), **self.auth_for("other")).status_code,
            404,
        )

    def test_idempotent_set_and_workout_completion(self):
        headers = self.auth()
        set_url = reverse("api_set_completion", args=[self.exercise.id, 2])
        self.assertTrue(self.client.put(set_url, **headers).json()["completed"])
        self.assertTrue(self.client.put(set_url, **headers).json()["completed"])
        self.assertFalse(self.client.delete(set_url, **headers).json()["completed"])
        self.assertFalse(self.client.delete(set_url, **headers).json()["completed"])
        self.assertEqual(
            self.client.put(reverse("api_set_completion", args=[self.exercise.id, 4]), **headers).status_code, 400
        )
        self.assertEqual(
            self.client.put(reverse("api_set_completion", args=[self.cardio.id, 2]), **headers).status_code, 400
        )

        workout_url = reverse("api_workout_completion", args=[self.week.id, self.workout.id])
        self.assertEqual(self.client.put(workout_url, **headers).json()["week_tally"]["completed"], 1)
        self.assertEqual(self.client.put(workout_url, **headers).json()["week_tally"]["completed"], 1)
        self.assertEqual(self.client.delete(workout_url, **headers).json()["week_tally"]["completed"], 0)
        self.assertEqual(self.client.delete(workout_url, **headers).json()["week_tally"]["completed"], 0)

    def test_auth_and_public_documentation(self):
        self.assertEqual(self.client.get(reverse("api_me")).status_code, 401)
        self.assertEqual(self.client.get(reverse("api_schema")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api_docs")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api_redoc")).status_code, 200)

    # --- Offline sync, client dates and time zones -------------------------

    def event(self, type_, minutes, log_date="2026-09-28", **fields):
        import uuid
        from datetime import datetime, timedelta
        from datetime import timezone as dt_timezone

        occurred = datetime(2026, 9, 28, 18, 0, tzinfo=dt_timezone.utc) + timedelta(minutes=minutes)
        return {"id": str(uuid.uuid4()), "type": type_, "log_date": log_date, "occurred_at": occurred.isoformat(), **fields}

    def sync(self, events, headers=None):
        return self.client.post(
            reverse("api_sync"), {"events": events}, content_type="application/json", **(headers or self.auth())
        )

    def test_sync_applies_events_on_client_dates_and_is_idempotent(self):
        from training.models import CompletedSet, WorkoutCompletion

        events = [
            self.event("set_completed", 0, exercise_id=self.exercise.id, set_number=1),
            self.event("set_completed", 1, exercise_id=self.exercise.id, set_number=2),
            self.event(
                "workout_completed",
                2,
                workout_id=self.workout.id,
                week_id=self.week.id,
                started_at="2026-09-28T17:00:00Z",
                ended_at="2026-09-28T18:02:00Z",
            ),
        ]
        response = self.sync(events)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["status"] for r in response.json()["results"]], ["applied"] * 3)
        self.assertEqual(
            sorted(CompletedSet.objects.filter(log_date="2026-09-28").values_list("set_number", flat=True)), [1, 2]
        )
        completion = WorkoutCompletion.objects.get(log_date="2026-09-28")
        self.assertIsNotNone(completion.started_at)
        self.assertEqual(completion.week, self.week)

        replay = self.sync(events)
        self.assertEqual([r["status"] for r in replay.json()["results"]], ["duplicate"] * 3)
        self.assertEqual(CompletedSet.objects.count(), 2)

        day = self.client.get(reverse("api_workout", args=[self.workout.id]) + "?date=2026-09-28", **self.auth())
        self.assertEqual(day.json()["exercises"][0]["completed_set_numbers"], [1, 2])
        self.assertTrue(day.json()["workout_completed"])

    def test_sync_last_write_wins_regardless_of_arrival_order(self):
        from training.models import CompletedSet

        newer_clear = self.event("set_cleared", 10, exercise_id=self.exercise.id, set_number=1)
        older_check = self.event("set_completed", 5, exercise_id=self.exercise.id, set_number=1)
        self.assertEqual(self.sync([newer_clear]).json()["results"][0]["status"], "applied")
        # The older check arrives later (e.g. from a second device) and must not win.
        self.assertEqual(self.sync([older_check]).json()["results"][0]["status"], "stale")
        self.assertFalse(CompletedSet.objects.exists())

        # Within one batch, events are applied in occurred_at order.
        later_check = self.event("set_completed", 20, exercise_id=self.exercise.id, set_number=2)
        earlier_clear = self.event("set_cleared", 15, exercise_id=self.exercise.id, set_number=2)
        statuses = [r["status"] for r in self.sync([later_check, earlier_clear]).json()["results"]]
        self.assertEqual(statuses, ["applied", "applied"])
        self.assertTrue(CompletedSet.objects.filter(set_number=2).exists())

    def test_online_changes_participate_in_last_write_wins(self):
        from training.models import CompletedSet

        # Checked online "now"; a queued clear from earlier in the past is stale.
        today = self.client.get(reverse("api_me"), **self.auth()).json()["today"]
        self.client.put(reverse("api_set_completion", args=[self.exercise.id, 1]), **self.auth())
        old_clear = self.event("set_cleared", 0, log_date=today, exercise_id=self.exercise.id, set_number=1)
        self.assertEqual(self.sync([old_clear]).json()["results"][0]["status"], "stale")
        self.assertTrue(CompletedSet.objects.filter(set_number=1).exists())

    def test_sync_rejects_bad_events_without_failing_batch(self):
        other_plan = Plan.objects.create(trainer=self.trainer, name="Not mine")
        foreign = Workout.objects.create(plan=other_plan, name="Foreign")
        foreign_ex = Exercise.objects.create(workout=foreign, segment="Main", name="X", sets_count=3)
        events = [
            {"id": "not-a-uuid", "type": "set_completed"},
            self.event("set_completed", 0, exercise_id=foreign_ex.id, set_number=1),
            self.event("set_completed", 1, exercise_id=self.exercise.id, set_number=9),
            self.event("set_completed", 2, log_date="2099-01-01", exercise_id=self.exercise.id, set_number=1),
            self.event("workout_completed", 3, workout_id=self.workout.id),  # missing week_id
            self.event("set_completed", 4, exercise_id=self.exercise.id, set_number=3),
        ]
        results = self.sync(events).json()["results"]
        self.assertEqual([r["status"] for r in results], ["rejected"] * 5 + ["applied"])
        self.assertIn("week_id", results[4]["errors"])

    def test_sync_batch_limit(self):
        events = [self.event("set_completed", i, exercise_id=self.exercise.id, set_number=1) for i in range(501)]
        self.assertEqual(self.sync(events).status_code, 400)

    def test_dates_follow_user_time_zone(self):
        headers = self.auth()
        bad = self.client.patch(reverse("api_me"), {"timezone": "Mars/Base"}, content_type="application/json", **headers)
        self.assertEqual(bad.status_code, 400)
        ok = self.client.patch(
            reverse("api_me"), {"timezone": "Pacific/Kiritimati"}, content_type="application/json", **headers
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["timezone"], "Pacific/Kiritimati")
        from training.completions import user_today

        self.user.refresh_from_db()
        self.assertEqual(ok.json()["today"], user_today(self.user).isoformat())

    def test_date_params_and_history(self):
        headers = self.auth()
        url = reverse("api_set_completion", args=[self.exercise.id, 1])
        self.assertEqual(self.client.put(url + "?date=2026-09-01", **headers).status_code, 200)
        self.assertEqual(self.client.put(url + "?date=2099-01-01", **headers).status_code, 400)
        self.assertEqual(self.client.put(url + "?date=nope", **headers).status_code, 400)

        workout_url = reverse("api_workout_completion", args=[self.week.id, self.workout.id]) + "?date=2026-09-01"
        done = self.client.put(
            workout_url,
            {"started_at": "2026-09-01T12:00:00Z", "ended_at": "2026-09-01T11:00:00Z"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(done.status_code, 400)  # ended before started
        self.assertEqual(self.client.put(workout_url, **headers).status_code, 200)

        schedule = self.client.get(reverse("api_active_schedule") + "?date=2026-09-03", **headers).json()
        self.assertEqual(schedule["phases"][0]["weeks"][0]["week_tally"]["completed"], 1)

        history = self.client.get(reverse("api_history") + "?from=2026-08-25&to=2026-09-30", **headers).json()
        self.assertEqual(history["workouts"][0]["date"], "2026-09-01")
        self.assertEqual(history["sets_completed_by_date"], {"2026-09-01": 1})
        self.assertEqual(
            self.client.get(reverse("api_history") + "?from=2024-01-01&to=2026-01-01", **headers).status_code, 400
        )
