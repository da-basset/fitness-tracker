from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Client, Gym, Trainer
from training.models import Exercise, Phase, Plan, PlanAssignment, Week, WeekDay, Workout

User = get_user_model()


class NativeApiTests(TestCase):
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

    def auth_for(self, username):
        response = self.token_pair(username)
        self.assertEqual(response.status_code, 200)
        return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['access']}"}

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
