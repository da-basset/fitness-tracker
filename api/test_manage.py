import json

from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Client, Trainer
from training.models import (
    MAX_PHASES,
    Exercise,
    Nutrient,
    Phase,
    Plan,
    PlanAssignment,
    Supplement,
    Week,
    WeekDay,
    Workout,
)

from . import serializers as api_serializers
from .tests import NativeApiTestCase

User = get_user_model()
STRONG = "Str0ng-pass-phrase!"


class ResponseSchemaTests(NativeApiTestCase):
    """The client endpoints build plain dicts; their schema serializers must
    describe exactly those dicts or the app's generated types lie."""

    def assertShape(self, serializer_class, url):
        body = self.client.get(url, **self.auth()).json()
        rendered = json.loads(json.dumps(serializer_class(body).data))
        self.assertEqual(rendered, body)

    def test_client_responses_match_schema(self):
        self.client.put(reverse("api_set_completion", args=[self.exercise.id, 1]), **self.auth())
        self.client.put(reverse("api_workout_completion", args=[self.week.id, self.workout.id]), **self.auth())
        self.assertShape(api_serializers.MeSerializer, reverse("api_me"))
        self.assertShape(api_serializers.ActivePlanSerializer, reverse("api_active_plan"))
        self.assertShape(api_serializers.ScheduleSerializer, reverse("api_active_schedule"))
        self.assertShape(api_serializers.ClientWorkoutSerializer, reverse("api_workout", args=[self.workout.id]))
        self.assertShape(api_serializers.HistorySerializer, reverse("api_history") + "?from=2026-01-01&to=2026-12-31")


class ManageApiTests(NativeApiTestCase):
    def setUp(self):
        super().setUp()
        # A second gym whose owner/trainer must never see the first gym's data.
        self.other_owner = User.objects.create_user("other_owner", password="pw")
        other_gym = self.gym.__class__.objects.create(name="Elsewhere", owner=self.other_owner)
        self.other_trainer_user = User.objects.create_user("other_trainer", password="pw")
        self.other_trainer = Trainer.objects.create(user=self.other_trainer_user, gym=other_gym)
        self.template = Plan.objects.create(trainer=self.trainer, name="Template")
        push = Workout.objects.create(plan=self.template, name="Push", order=1)
        Exercise.objects.create(workout=push, segment="Main", name="Press", sets_count=3, order=1)
        phase = Phase.objects.create(plan=self.template, title="Base", order=1)
        week = Week.objects.create(phase=phase, order=1)
        WeekDay.objects.create(week=week, weekday="Tue", workout=push)
        Nutrient.objects.create(plan=self.template, name="Protein", amount="180g")

    def call(self, method, url, user="trainer", data=None):
        kwargs = {"content_type": "application/json", **self.auth_for(user)}
        if data is not None:
            kwargs["data"] = json.dumps(data)
        return getattr(self.client, method)(url, **kwargs)

    # --- people ---

    def test_trainer_and_client_lists_follow_roles(self):
        trainers = self.call("get", reverse("api_trainers"), "owner").json()
        self.assertEqual([t["username"] for t in trainers], ["trainer"])
        self.assertEqual(self.call("get", reverse("api_trainers"), "trainer").json()[0]["id"], self.trainer.id)
        self.assertEqual(self.call("get", reverse("api_trainers"), "client").json(), [])

        clients = self.call("get", reverse("api_clients"), "owner").json()
        self.assertEqual(clients[0]["active_plan"]["plan_name"], "Native plan")
        self.assertEqual(self.call("get", reverse("api_clients"), "other_trainer").json(), [])

    def test_owner_creates_trainer_with_web_validation(self):
        weak = self.call("post", reverse("api_trainers"), "owner", {"username": "t2", "password": "123"})
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.json())
        taken = self.call("post", reverse("api_trainers"), "owner", {"username": "trainer", "password": STRONG})
        self.assertIn("username", taken.json())

        created = self.call(
            "post", reverse("api_trainers"), "owner", {"username": "t2", "password": STRONG, "first_name": "Tia"}
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["name"], "Tia")
        self.assertTrue(Trainer.objects.filter(user__username="t2", gym=self.gym).exists())
        self.assertEqual(self.token_pair("t2", STRONG).status_code, 200)

        self.assertEqual(
            self.call("post", reverse("api_trainers"), "trainer", {"username": "t3", "password": STRONG}).status_code,
            403,
        )

    def test_trainer_creates_client(self):
        created = self.call("post", reverse("api_clients"), "trainer", {"username": "c2", "password": STRONG})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(Client.objects.get(user__username="c2").trainer, self.trainer)
        self.assertEqual(
            self.call("post", reverse("api_clients"), "client", {"username": "c3", "password": STRONG}).status_code,
            403,
        )

    def test_client_detail_access(self):
        url = reverse("api_client_detail", args=[self.client_profile.id])
        detail = self.call("get", url, "owner").json()
        self.assertEqual(detail["active_assignment"]["plan_name"], "Native plan")
        self.assertEqual([t["name"] for t in detail["templates"]], ["Template"])
        self.assertEqual(detail["stats"]["all_time_completed"], 0)
        self.assertEqual(self.call("get", url, "other_owner").status_code, 404)
        self.assertEqual(self.call("get", url, "client").status_code, 404)

    # --- plan library ---

    def test_library_create_assign_unassign_delete(self):
        library = reverse("api_plan_library", args=[self.trainer.id])
        self.assertEqual([p["name"] for p in self.call("get", library).json()], ["Template"])
        self.assertEqual(self.call("get", library, "other_trainer").status_code, 404)

        created = self.call("post", library, data={"name": "Fresh"})
        self.assertEqual(created.status_code, 201)
        fresh_id = created.json()["id"]
        self.assertEqual(self.call("delete", reverse("api_plan_detail", args=[fresh_id])).status_code, 204)

        assigned = self.call(
            "post", reverse("api_plan_assign", args=[self.template.id]), data={"client_id": self.client_profile.id}
        )
        self.assertEqual(assigned.status_code, 201)
        clone = Plan.objects.get(pk=assigned.json()["plan_id"])
        self.assertEqual(clone.source_plan, self.template)
        self.assertEqual(clone.workouts.get().exercises.get().name, "Press")
        self.assertEqual(clone.nutrients.get().name, "Protein")
        self.assertFalse(PlanAssignment.objects.get(pk=self.assignment.pk).is_active)
        # The client's app now follows the clone.
        self.assertEqual(self.client.get(reverse("api_active_plan"), **self.auth()).json()["id"], clone.id)

        # Assigned plans are history and can't be deleted.
        self.assertEqual(self.call("delete", reverse("api_plan_detail", args=[clone.id])).status_code, 400)

        unassigned = self.call("post", reverse("api_unassign", args=[assigned.json()["id"]]))
        self.assertFalse(unassigned.json()["is_active"])
        self.assertEqual(self.client.get(reverse("api_active_plan"), **self.auth()).status_code, 404)

    def test_assign_rejects_other_trainers_client(self):
        stranger = Client.objects.create(
            user=User.objects.create_user("stranger", password="pw"), trainer=self.other_trainer
        )
        response = self.call("post", reverse("api_plan_assign", args=[self.template.id]), data={"client_id": stranger.id})
        self.assertEqual(response.status_code, 400)

    def test_plan_detail_visibility(self):
        url = reverse("api_plan_detail", args=[self.plan.id])
        detail = self.call("get", url, "owner").json()
        self.assertTrue(detail["can_manage"])
        self.assertFalse(detail["is_template"])
        self.assertEqual(detail["owning_client"]["name"], "client")
        self.assertEqual(detail["phases"][0]["weeks"][0]["days"]["Mon"], self.workout.id)
        self.assertIsNone(detail["phases"][0]["weeks"][0]["days"]["Tue"])
        # The client may view (not manage) their own plan.
        mine = self.call("get", url, "client")
        self.assertEqual(mine.status_code, 200)
        self.assertFalse(mine.json()["can_manage"])
        self.assertEqual(self.call("get", url, "other_trainer").status_code, 404)

    # --- plan editor ---

    def test_editor_requires_manage_permission(self):
        url = reverse("api_plan_workouts", args=[self.plan.id])
        self.assertEqual(self.call("post", url, "client", {"name": "Sneaky"}).status_code, 404)
        self.assertEqual(self.call("post", url, "other_owner", {"name": "Sneaky"}).status_code, 404)
        self.assertEqual(self.call("post", url, "owner", {"name": "Legit"}).status_code, 201)

    def test_workout_and_exercise_crud(self):
        workout = self.call("post", reverse("api_plan_workouts", args=[self.plan.id]), data={"name": "Pull", "color": "blue"})
        self.assertEqual(workout.status_code, 201)
        workout_id = workout.json()["id"]
        self.assertEqual(workout.json()["order"], 2)
        self.assertEqual(
            self.call("post", reverse("api_plan_workouts", args=[self.plan.id]), data={"name": "X", "color": "plaid"}).status_code,
            400,
        )

        exercises_url = reverse("api_plan_exercises", args=[self.plan.id, workout_id])
        bad = self.call("post", exercises_url, data={"name": "Row", "segment": "Main", "sets_count": 50})
        self.assertIn("sets_count", bad.json())
        self.assertIn("segment", self.call("post", exercises_url, data={"name": "Row", "segment": "Nap"}).json())
        row = self.call("post", exercises_url, data={"name": "Row", "segment": "Main", "sets_count": 4, "rest_seconds": 90})
        curl = self.call("post", exercises_url, data={"name": "Curl", "segment": "Main"})
        self.assertEqual(row.status_code, 201)
        self.assertTrue(row.json()["is_custom"])

        edit_url = reverse("api_plan_exercise_edit", args=[self.plan.id, row.json()["id"]])
        self.assertEqual(self.call("patch", edit_url, data={"reps_text": "8-10"}).json()["reps_text"], "8-10")

        reorder_url = reverse("api_plan_exercises_reorder", args=[self.plan.id, workout_id])
        self.assertEqual(self.call("post", reorder_url, data={"order": [row.json()["id"]]}).status_code, 400)
        reordered = self.call("post", reorder_url, data={"order": [curl.json()["id"], row.json()["id"]]})
        self.assertEqual([e["name"] for e in reordered.json()], ["Curl", "Row"])

        self.assertEqual(self.call("delete", edit_url).status_code, 204)
        # An exercise from another plan is out of reach through this plan.
        foreign = reverse("api_plan_exercise_edit", args=[self.plan.id, self.template.workouts.get().exercises.get().id])
        self.assertEqual(self.call("patch", foreign, data={"name": "Hijack"}).status_code, 404)

        rename = self.call(
            "patch", reverse("api_plan_workout_edit", args=[self.plan.id, workout_id]), data={"name": "Pull Day"}
        )
        self.assertEqual(rename.json()["name"], "Pull Day")
        self.assertEqual(
            self.call("delete", reverse("api_plan_workout_edit", args=[self.plan.id, workout_id])).status_code, 204
        )

    def test_phases_weeks_and_schedule(self):
        phase = self.call("post", reverse("api_plan_phases", args=[self.plan.id]), data={"title": "Build"})
        self.assertEqual(phase.status_code, 201)
        self.assertEqual(len(phase.json()["weeks"]), 1)
        phase_id = phase.json()["id"]
        week_id = phase.json()["weeks"][0]["id"]

        week_url = reverse("api_plan_week_edit", args=[self.plan.id, week_id])
        set_days = self.call("patch", week_url, data={"days": {"Wed": self.workout.id, "Fri": None}})
        self.assertEqual(set_days.json()["days"]["Wed"], self.workout.id)
        foreign_workout = self.template.workouts.get().id
        self.assertIn("days", self.call("patch", week_url, data={"days": {"Thu": foreign_workout}}).json())
        self.assertIn("days", self.call("patch", week_url, data={"days": {"Someday": None}}).json())

        # The last week of a phase can't be removed; a second one can.
        self.assertEqual(self.call("delete", week_url).status_code, 400)
        second = self.call("post", reverse("api_plan_weeks", args=[self.plan.id, phase_id]))
        self.assertEqual(second.status_code, 201)
        self.assertEqual(self.call("delete", week_url).status_code, 204)

        phase_url = reverse("api_plan_phase_edit", args=[self.plan.id, phase_id])
        self.assertEqual(self.call("patch", phase_url, data={"title": "Peak"}).json()["title"], "Peak")
        self.assertEqual(self.call("delete", phase_url).status_code, 204)

    def test_phase_limit(self):
        for index in range(MAX_PHASES - self.plan.phases.count()):
            Phase.objects.create(plan=self.plan, title=f"P{index}", order=index + 10)
        response = self.call("post", reverse("api_plan_phases", args=[self.plan.id]), data={"title": "One too many"})
        self.assertEqual(response.status_code, 400)

    def test_nutrients_and_supplements(self):
        cases = (
            ("api_plan_nutrients", "api_plan_nutrient_edit", Nutrient),
            ("api_plan_supplements", "api_plan_supplement_edit", Supplement),
        )
        for list_name, edit_name, model in cases:
            created = self.call("post", reverse(list_name, args=[self.plan.id]), data={"name": "Thing", "amount": "5g"})
            self.assertEqual(created.status_code, 201)
            edit_url = reverse(edit_name, args=[self.plan.id, created.json()["id"]])
            self.assertEqual(self.call("patch", edit_url, data={"timing": "Morning"}).json()["timing"], "Morning")
            self.assertEqual(self.call("patch", edit_url, "client", {"timing": "Never"}).status_code, 404)
            self.assertEqual(self.call("delete", edit_url).status_code, 204)
            self.assertFalse(model.objects.filter(plan=self.plan).exists())
