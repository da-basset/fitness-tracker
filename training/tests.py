"""Permission-matrix + clone-independence tests for the trainer/owner
plan-editing redesign. Uses its own fixtures (fresh Gym/Trainer/Client
trees) rather than depending on any particular real data, so this suite
is safe to run against the throwaway test database `manage.py test`
always creates."""

from django.contrib.auth import get_user_model
from django.test import Client as HttpClient
from django.test import TestCase
from django.urls import reverse

from accounts.models import Client as ClientProfile
from accounts.models import Gym, Trainer
from training.models import Exercise, Nutrient, Phase, Plan, PlanAssignment, Supplement, Week, WeekDay, Workout
from training.services import clone_plan_for_client

User = get_user_model()


def make_gym_trainer_client(gym_owner_username, trainer_username, client_username):
    owner = User.objects.create_user(gym_owner_username, password="pw")
    gym = Gym.objects.create(name=f"{gym_owner_username}'s Gym", owner=owner)
    trainer_user = User.objects.create_user(trainer_username, password="pw")
    trainer = Trainer.objects.create(user=trainer_user, gym=gym)
    client_user = User.objects.create_user(client_username, password="pw")
    client = ClientProfile.objects.create(user=client_user, trainer=trainer)
    return owner, gym, trainer, client


def make_simple_plan(trainer, name="Test Plan"):
    plan = Plan.objects.create(trainer=trainer, name=name)
    workout = Workout.objects.create(plan=plan, name="Push", order=1)
    Exercise.objects.create(workout=workout, segment="Main", name="Bench Press", sets_count=3, order=1)
    phase = Phase.objects.create(plan=plan, title="Block 1", order=1)
    week = Week.objects.create(phase=phase, order=1)
    WeekDay.objects.create(week=week, weekday="Mon", workout=workout)
    Nutrient.objects.create(plan=plan, name="Protein", amount="180g/day", order=1)
    Supplement.objects.create(plan=plan, name="Creatine", amount="5g", timing="Morning", order=1)
    return plan


class PermissionMatrixTests(TestCase):
    """Only a Trainer themselves, or the Owner of their Gym, may manage a
    plan's workouts/phases/exercises/schedule -- nobody else, including
    the plan's own assigned client, gets write access."""

    def setUp(self):
        self.owner1, self.gym1, self.trainer1, self.client1 = make_gym_trainer_client(
            "owner1", "trainer1", "client1"
        )
        self.owner2, self.gym2, self.trainer2, self.client2 = make_gym_trainer_client(
            "owner2", "trainer2", "client2"
        )
        self.template = make_simple_plan(self.trainer1)
        self.assigned_plan = clone_plan_for_client(self.template, self.client1)
        PlanAssignment.objects.create(plan=self.assigned_plan, client=self.client1, is_active=True)
        self.workout = self.assigned_plan.workouts.first()
        self.exercise = self.workout.exercises.first()
        self.nutrient = self.assigned_plan.nutrients.first()
        self.supplement = self.assigned_plan.supplements.first()

    def login(self, username):
        c = HttpClient()
        c.force_login(User.objects.get(username=username))
        return c

    def test_trainer_can_manage_own_plan(self):
        c = self.login("trainer1")
        resp = c.get(reverse("plan_detail", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(
            reverse("api_plan_create_exercise", args=[self.assigned_plan.id, self.workout.id]),
            data='{"name": "Row", "segment": "Main"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_owner_can_manage_trainers_plan(self):
        c = self.login("owner1")
        resp = c.get(reverse("plan_detail", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(
            reverse("api_plan_reorder_exercises", args=[self.assigned_plan.id, self.workout.id]),
            data=f'{{"order": [{self.exercise.id}]}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_other_trainer_and_owner_404(self):
        for username in ("trainer2", "owner2"):
            c = self.login(username)
            resp = c.get(reverse("plan_detail", args=[self.assigned_plan.id]))
            self.assertEqual(resp.status_code, 404, username)
            resp = c.get(reverse("plan_manage", args=[self.assigned_plan.id]))
            self.assertEqual(resp.status_code, 404, username)

    def test_client_cannot_write_even_to_their_own_assigned_plan(self):
        """The gap this whole redesign closes: a client used to be able to
        add/edit/delete/reorder exercises on their own active plan."""
        c = self.login("client1")
        resp = c.post(
            reverse("api_plan_create_exercise", args=[self.assigned_plan.id, self.workout.id]),
            data='{"name": "Sneaky", "segment": "Main"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        resp = c.post(
            reverse("api_plan_reorder_exercises", args=[self.assigned_plan.id, self.workout.id]),
            data=f'{{"order": [{self.exercise.id}]}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        resp = c.delete(reverse("api_plan_exercise_detail", args=[self.assigned_plan.id, self.exercise.id]))
        self.assertEqual(resp.status_code, 404)
        # Also can't reach the trainer's editing pages for their own plan.
        resp = c.get(reverse("plan_detail", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)
        resp = c.get(reverse("plan_manage", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)

    def test_client_can_view_but_not_manage_own_plan(self):
        c = self.login("client1")
        resp = c.get(reverse("api_plan_schedule", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.get(reverse("api_plan_workout", args=[self.assigned_plan.id, self.workout.id]))
        self.assertEqual(resp.status_code, 200)

    def test_unrelated_client_cannot_view(self):
        c = self.login("client2")
        resp = c.get(reverse("api_plan_schedule", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)

    def test_client_view_preview_is_trainer_owner_only(self):
        for username, expected in (("trainer1", 200), ("owner1", 200), ("client1", 404), ("trainer2", 404)):
            c = self.login(username)
            resp = c.get(reverse("plan_preview", args=[self.assigned_plan.id]))
            self.assertEqual(resp.status_code, expected, username)

    def test_workout_edit_page_wires_up_single_workout_exercise_editor(self):
        """Regression test for the gap where a trainer could create a
        Workout at /manage/workouts/<id>/ but had no way to add exercises
        to it unless it was already scheduled on a day somewhere. The page
        now embeds a "workout" mode TRAINING_CONFIG that lets the shared
        training.js drive that one workout's exercise editor directly."""
        c = self.login("trainer1")
        resp = c.get(reverse("workout_edit", args=[self.workout.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mode: "workout"')
        self.assertContains(resp, f"workoutId: {self.workout.id}")
        self.assertContains(resp, f"/training/plans/{self.assigned_plan.id}/api/workouts/__ID__/exercises/")

    def test_plan_workout_create_is_a_single_hop_straight_to_the_exercise_editor(self):
        """plan_workout_create used to render its own bare "name/color
        only" form/page first, and only after that redirected to
        workout_edit -- two near-identical pages for one workout, with no
        way to add exercises until the first page was submitted. It now
        creates the row immediately (POST, no body needed) and redirects
        straight to workout_edit, whose exercise editor is already live
        with nothing else required first."""
        c = self.login("trainer1")
        before_count = self.assigned_plan.workouts.count()

        resp = c.post(reverse("plan_workout_create", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.assigned_plan.workouts.count(), before_count + 1)
        new_workout = self.assigned_plan.workouts.latest("id")
        self.assertEqual(resp.url, reverse("workout_edit", args=[new_workout.id]))

        resp = c.get(resp.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mode: "workout"')
        self.assertContains(resp, f"workoutId: {new_workout.id}")

        # A plain GET (link prefetch, browser back/forward) must never
        # create a row -- only the POST above does.
        before_count = self.assigned_plan.workouts.count()
        resp = c.get(reverse("plan_workout_create", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("plan_manage", args=[self.assigned_plan.id]))
        self.assertEqual(self.assigned_plan.workouts.count(), before_count)

    def test_other_trainer_and_owner_404_on_workout_edit(self):
        for username in ("trainer2", "owner2"):
            c = self.login(username)
            resp = c.get(reverse("workout_edit", args=[self.workout.id]))
            self.assertEqual(resp.status_code, 404, username)

    def test_client_cannot_reach_workout_edit(self):
        c = self.login("client1")
        resp = c.get(reverse("workout_edit", args=[self.workout.id]))
        self.assertEqual(resp.status_code, 404)

    def test_trainer_can_delete_own_unassigned_template(self):
        c = self.login("trainer1")
        template_id = self.template.id
        resp = c.get(reverse("plan_delete", args=[template_id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(reverse("plan_delete", args=[template_id]))
        self.assertRedirects(resp, reverse("plan_library", args=[self.trainer1.id]))
        self.assertFalse(Plan.objects.filter(id=template_id).exists())

    def test_owner_can_delete_trainers_unassigned_template(self):
        c = self.login("owner1")
        template_id = self.template.id
        resp = c.post(reverse("plan_delete", args=[template_id]))
        self.assertRedirects(resp, reverse("plan_library", args=[self.trainer1.id]))
        self.assertFalse(Plan.objects.filter(id=template_id).exists())

    def test_other_trainer_and_owner_404_deleting_template(self):
        for username in ("trainer2", "owner2"):
            c = self.login(username)
            resp = c.get(reverse("plan_delete", args=[self.template.id]))
            self.assertEqual(resp.status_code, 404, username)
            resp = c.post(reverse("plan_delete", args=[self.template.id]))
            self.assertEqual(resp.status_code, 404, username)
        self.assertTrue(Plan.objects.filter(id=self.template.id).exists())

    def test_client_cannot_delete_template(self):
        c = self.login("client1")
        resp = c.post(reverse("plan_delete", args=[self.template.id]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Plan.objects.filter(id=self.template.id).exists())

    def test_cannot_delete_a_plan_already_assigned_to_a_client(self):
        """A plan a client has (or once had) is history, not a library
        template -- it isn't deletable from here even by the trainer who
        owns it, to avoid silently wiping a client's plan/workout history."""
        c = self.login("trainer1")
        resp = c.get(reverse("plan_delete", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)
        resp = c.post(reverse("plan_delete", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Plan.objects.filter(id=self.assigned_plan.id).exists())


    def test_trainer_can_manage_nutrients_and_supplements(self):
        c = self.login("trainer1")
        resp = c.post(
            reverse("plan_nutrient_create", args=[self.assigned_plan.id]),
            data={"name": "Water", "amount": "1 gal/day", "timing": "", "notes": "", "order": 2},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Nutrient.objects.filter(plan=self.assigned_plan, name="Water").exists())

        resp = c.post(
            reverse("nutrient_edit", args=[self.nutrient.id]),
            data={"name": "Protein", "amount": "200g/day", "timing": "", "notes": "", "order": 1},
        )
        self.assertEqual(resp.status_code, 302)
        self.nutrient.refresh_from_db()
        self.assertEqual(self.nutrient.amount, "200g/day")

        resp = c.post(reverse("nutrient_delete", args=[self.nutrient.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Nutrient.objects.filter(id=self.nutrient.id).exists())

        resp = c.post(
            reverse("plan_supplement_create", args=[self.assigned_plan.id]),
            data={"name": "Fish Oil", "amount": "2g", "timing": "Evening", "notes": "", "order": 2},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Supplement.objects.filter(plan=self.assigned_plan, name="Fish Oil").exists())

        resp = c.post(reverse("supplement_delete", args=[self.supplement.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Supplement.objects.filter(id=self.supplement.id).exists())

    def test_other_trainer_and_owner_404_on_nutrient_and_supplement_writes(self):
        for username in ("trainer2", "owner2"):
            c = self.login(username)
            resp = c.get(reverse("plan_nutrient_create", args=[self.assigned_plan.id]))
            self.assertEqual(resp.status_code, 404, username)
            resp = c.post(reverse("nutrient_edit", args=[self.nutrient.id]), data={"name": "x"})
            self.assertEqual(resp.status_code, 404, username)
            resp = c.post(reverse("nutrient_delete", args=[self.nutrient.id]))
            self.assertEqual(resp.status_code, 404, username)
            resp = c.get(reverse("plan_supplement_create", args=[self.assigned_plan.id]))
            self.assertEqual(resp.status_code, 404, username)
            resp = c.post(reverse("supplement_edit", args=[self.supplement.id]), data={"name": "x"})
            self.assertEqual(resp.status_code, 404, username)
            resp = c.post(reverse("supplement_delete", args=[self.supplement.id]))
            self.assertEqual(resp.status_code, 404, username)
        self.assertTrue(Nutrient.objects.filter(id=self.nutrient.id).exists())
        self.assertTrue(Supplement.objects.filter(id=self.supplement.id).exists())

    def test_client_cannot_write_nutrients_or_supplements_on_their_own_plan(self):
        c = self.login("client1")
        resp = c.get(reverse("plan_nutrient_create", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)
        resp = c.post(reverse("nutrient_edit", args=[self.nutrient.id]), data={"name": "Sneaky"})
        self.assertEqual(resp.status_code, 404)
        resp = c.post(reverse("nutrient_delete", args=[self.nutrient.id]))
        self.assertEqual(resp.status_code, 404)
        resp = c.get(reverse("plan_supplement_create", args=[self.assigned_plan.id]))
        self.assertEqual(resp.status_code, 404)
        resp = c.post(reverse("supplement_edit", args=[self.supplement.id]), data={"name": "Sneaky"})
        self.assertEqual(resp.status_code, 404)
        resp = c.post(reverse("supplement_delete", args=[self.supplement.id]))
        self.assertEqual(resp.status_code, 404)
        self.nutrient.refresh_from_db()
        self.supplement.refresh_from_db()
        self.assertNotEqual(self.nutrient.name, "Sneaky")
        self.assertNotEqual(self.supplement.name, "Sneaky")

    def test_client_and_trainer_can_view_nutrients_and_supplements_on_plan_pages(self):
        """The plan pages themselves are static shells -- Nutrients/
        Supplements render as tabs via training.js, fed by the same
        schedule JSON endpoint the phase tabs use, so this checks that
        payload rather than server-rendered HTML."""
        for username, url in (
            ("client1", reverse("training_api_schedule")),
            ("trainer1", reverse("api_plan_schedule", args=[self.assigned_plan.id])),
            ("owner1", reverse("api_plan_schedule", args=[self.assigned_plan.id])),
        ):
            c = self.login(username)
            resp = c.get(url)
            self.assertEqual(resp.status_code, 200, username)
            data = resp.json()
            self.assertEqual([n["name"] for n in data["nutrients"]], ["Protein"], username)
            self.assertEqual([s["name"] for s in data["supplements"]], ["Creatine"], username)

        # And the pages themselves still load fine (the tabs/panel are
        # populated client-side from the payload above).
        for username, url in (
            ("client1", reverse("training_physical")),
            ("trainer1", reverse("plan_detail", args=[self.assigned_plan.id])),
        ):
            c = self.login(username)
            resp = c.get(url)
            self.assertEqual(resp.status_code, 200, username)


class ClonePlanTests(TestCase):
    """Assigning the same template to two clients must produce two fully
    independent copies -- editing one never touches the template or the
    other client's copy."""

    def setUp(self):
        self.owner, self.gym, self.trainer, self.client_a = make_gym_trainer_client(
            "owner3", "trainer3", "clienta"
        )
        user_b = User.objects.create_user("clientb", password="pw")
        self.client_b = ClientProfile.objects.create(user=user_b, trainer=self.trainer)
        self.template = make_simple_plan(self.trainer, name="Shared Template")

    def test_two_clones_are_independent(self):
        clone_a = clone_plan_for_client(self.template, self.client_a)
        clone_b = clone_plan_for_client(self.template, self.client_b)

        self.assertNotEqual(clone_a.id, clone_b.id)
        self.assertNotEqual(clone_a.id, self.template.id)
        self.assertEqual(clone_a.source_plan_id, self.template.id)
        self.assertEqual(clone_b.source_plan_id, self.template.id)

        # Structurally identical at clone time.
        self.assertEqual(clone_a.workouts.count(), self.template.workouts.count())
        self.assertEqual(clone_a.workouts.first().exercises.count(), 1)
        self.assertEqual(clone_b.workouts.first().exercises.count(), 1)

        # Editing clone_a's exercise must not affect clone_b or the template.
        ex_a = clone_a.workouts.first().exercises.first()
        ex_a.name = "Renamed only on A"
        ex_a.save()
        self.assertNotEqual(clone_b.workouts.first().exercises.first().name, "Renamed only on A")
        self.assertNotEqual(self.template.workouts.first().exercises.first().name, "Renamed only on A")

        # Adding an exercise to clone_b must not appear on clone_a or the template.
        Exercise.objects.create(workout=clone_b.workouts.first(), segment="Core", name="Only on B", order=2)
        self.assertEqual(clone_a.workouts.first().exercises.count(), 1)
        self.assertEqual(self.template.workouts.first().exercises.count(), 1)

    def test_template_stays_unassigned_and_is_library_template(self):
        self.assertTrue(self.template.is_library_template())
        clone = clone_plan_for_client(self.template, self.client_a)
        PlanAssignment.objects.create(plan=clone, client=self.client_a, is_active=True)
        self.assertTrue(self.template.is_library_template())
        self.assertFalse(clone.is_library_template())


    def test_nutrients_and_supplements_clone_independently(self):
        clone_a = clone_plan_for_client(self.template, self.client_a)
        clone_b = clone_plan_for_client(self.template, self.client_b)

        self.assertEqual(clone_a.nutrients.count(), self.template.nutrients.count())
        self.assertEqual(clone_a.supplements.count(), self.template.supplements.count())

        nutrient_a = clone_a.nutrients.first()
        nutrient_a.amount = "Changed only on A"
        nutrient_a.save()
        self.assertNotEqual(clone_b.nutrients.first().amount, "Changed only on A")
        self.assertNotEqual(self.template.nutrients.first().amount, "Changed only on A")

        Supplement.objects.create(plan=clone_b, name="Only on B", order=2)
        self.assertEqual(clone_a.supplements.count(), 1)
        self.assertEqual(self.template.supplements.count(), 1)


class ExistingPagesStillWorkTests(TestCase):
    """A light smoke pass over pages this redesign didn't intend to touch,
    plus the new /trainer and /client entry points."""

    def setUp(self):
        self.owner, self.gym, self.trainer, self.client = make_gym_trainer_client(
            "owner4", "trainer4", "client4"
        )
        self.plan = make_simple_plan(self.trainer)
        PlanAssignment.objects.create(plan=self.plan, client=self.client, is_active=True)

    def test_client_facing_pages_200(self):
        c = HttpClient()
        c.force_login(self.client.user)
        for name in ("training_hub", "training_physical", "training_spanish", "training_reading", "profile", "client_dashboard"):
            resp = c.get(reverse(name))
            self.assertEqual(resp.status_code, 200, name)

    def test_trainer_dashboard_and_client_detail(self):
        c = HttpClient()
        c.force_login(self.trainer.user)
        resp = c.get(reverse("trainer_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.client.user.username)
        resp = c.get(reverse("trainer_client_detail", args=[self.client.id]))
        self.assertEqual(resp.status_code, 200)

    def test_owner_sees_trainer_dashboard_too(self):
        c = HttpClient()
        c.force_login(self.owner)
        resp = c.get(reverse("trainer_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.client.user.username)

    def test_login_page_200_anonymous(self):
        c = HttpClient()
        resp = c.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)


class PlanLibraryWorkflowTests(TestCase):
    """End-to-end walk of the real view layer: create a template in the
    library, build it out via plan_manage/workout/phase forms, assign it
    to two different clients, and confirm each gets an independent copy
    plus the client's own dashboard and history page render."""

    def setUp(self):
        self.owner, self.gym, self.trainer, self.client_a = make_gym_trainer_client(
            "lib_owner", "lib_trainer", "lib_clienta"
        )
        user_b = User.objects.create_user("lib_clientb", password="pw")
        self.client_b = ClientProfile.objects.create(user=user_b, trainer=self.trainer)

    def test_full_library_to_assignment_flow(self):
        c = HttpClient()
        c.force_login(self.trainer.user)

        resp = c.get(reverse("plan_library", args=[self.trainer.id]))
        self.assertEqual(resp.status_code, 200)

        resp = c.post(reverse("plan_create", args=[self.trainer.id]), data={"name": "New Template", "description": "desc"})
        self.assertEqual(resp.status_code, 302)
        template = Plan.objects.get(name="New Template")
        self.assertTrue(template.is_library_template())

        resp = c.get(reverse("plan_manage", args=[template.id]))
        self.assertEqual(resp.status_code, 200)

        resp = c.post(reverse("plan_workout_create", args=[template.id]))
        self.assertEqual(resp.status_code, 302)
        workout = template.workouts.get()
        # Creating a workout drops you straight onto its own edit page --
        # exercises can be added there right away, not just after the fact.
        self.assertEqual(resp.url, reverse("workout_edit", args=[workout.id]))

        resp = c.get(reverse("workout_edit", args=[workout.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mode: "workout"')

        # Rename it from the same edit page (no detour through a separate
        # "add workout" form).
        resp = c.post(
            reverse("workout_edit", args=[workout.id]),
            data={"name": "Legs", "sub": "", "flavor": "", "color": "red"},
        )
        self.assertEqual(resp.status_code, 302)
        workout.refresh_from_db()
        self.assertEqual(workout.name, "Legs")

        resp = c.post(
            reverse("api_plan_create_exercise", args=[template.id, workout.id]),
            data='{"name": "Squat", "segment": "Main", "sets_count": 5, "reps_text": "5"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(workout.exercises.count(), 1)

        resp = c.post(reverse("plan_phase_create", args=[template.id]), data={"title": "Phase 1", "order": 1, "note": ""})
        self.assertEqual(resp.status_code, 302)

        # Assign to both clients -- each should get its own independent Plan.
        resp = c.get(reverse("plan_assign", args=[template.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(reverse("plan_assign", args=[template.id]), data={"client_id": self.client_a.id})
        self.assertEqual(resp.status_code, 302)
        resp = c.post(reverse("plan_assign", args=[template.id]), data={"client_id": self.client_b.id})
        self.assertEqual(resp.status_code, 302)

        plan_a = PlanAssignment.objects.get(client=self.client_a, is_active=True).plan
        plan_b = PlanAssignment.objects.get(client=self.client_b, is_active=True).plan
        self.assertNotEqual(plan_a.id, plan_b.id)
        self.assertEqual(plan_a.source_plan_id, template.id)
        self.assertTrue(template.is_library_template())  # still zero assignments of its own

        # Un-assign client A and confirm history still resolves.
        assignment_a = PlanAssignment.objects.get(client=self.client_a, is_active=True)
        resp = c.post(reverse("plan_unassign", args=[assignment_a.id]))
        self.assertEqual(resp.status_code, 302)
        assignment_a.refresh_from_db()
        self.assertFalse(assignment_a.is_active)

        client_a_http = HttpClient()
        client_a_http.force_login(self.client_a.user)
        resp = client_a_http.get(reverse("client_dashboard"))
        self.assertEqual(resp.status_code, 200)
        resp = client_a_http.get(reverse("client_plan_history", args=[assignment_a.id]))
        self.assertEqual(resp.status_code, 200)

        # The template itself never accumulates assignments of its own
        # (clients get clones, not the template) -- the library page still
        # offers it for deletion even after it's been used repeatedly, and
        # deleting it doesn't touch either client's own copy or history.
        resp = c.get(reverse("plan_library", args=[self.trainer.id]))
        self.assertContains(resp, reverse("plan_delete", args=[template.id]))
        resp = c.post(reverse("plan_delete", args=[template.id]))
        self.assertRedirects(resp, reverse("plan_library", args=[self.trainer.id]))
        self.assertFalse(Plan.objects.filter(id=template.id).exists())
        plan_a.refresh_from_db()
        plan_b.refresh_from_db()
        self.assertIsNone(plan_a.source_plan_id)
        self.assertIsNone(plan_b.source_plan_id)
        resp = client_a_http.get(reverse("client_plan_history", args=[assignment_a.id]))
        self.assertEqual(resp.status_code, 200)


class StructuralEditorCoverageTests(TestCase):
    """Touches the remaining workout/phase/week CRUD views (confirm-delete
    pages, phase editing with its week-day grid, week add/remove) that the
    other suites don't happen to exercise, to confirm the plan-id
    re-scoping didn't silently break any of them."""

    def setUp(self):
        self.owner, self.gym, self.trainer, self.client = make_gym_trainer_client(
            "struct_owner", "struct_trainer", "struct_client"
        )
        self.plan = make_simple_plan(self.trainer)
        self.workout = self.plan.workouts.first()
        self.phase = self.plan.phases.first()
        self.week = self.phase.weeks.first()

    def test_workout_delete_confirm_and_post(self):
        c = HttpClient()
        c.force_login(self.trainer.user)
        resp = c.get(reverse("workout_delete", args=[self.workout.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(reverse("workout_delete", args=[self.workout.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Workout.objects.filter(pk=self.workout.id).exists())

    def test_phase_edit_and_week_add_remove(self):
        c = HttpClient()
        c.force_login(self.trainer.user)
        resp = c.get(reverse("phase_edit", args=[self.phase.id]))
        self.assertEqual(resp.status_code, 200)

        resp = c.post(reverse("week_create", args=[self.phase.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.phase.weeks.count(), 2)

        new_week = self.phase.weeks.exclude(pk=self.week.id).first()
        resp = c.post(
            reverse("phase_edit", args=[self.phase.id]),
            data={
                "title": self.phase.title,
                "order": self.phase.order,
                "note": self.phase.note,
                f"day_week{self.week.id}_Mon": str(self.workout.id),
                f"day_week{new_week.id}_Mon": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.week.days.get(weekday="Mon").workout_id, self.workout.id)

        resp = c.get(reverse("week_delete", args=[new_week.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(reverse("week_delete", args=[new_week.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.phase.weeks.count(), 1)

    def test_phase_delete_confirm_and_post(self):
        c = HttpClient()
        c.force_login(self.trainer.user)
        resp = c.get(reverse("phase_delete", args=[self.phase.id]))
        self.assertEqual(resp.status_code, 200)
        resp = c.post(reverse("phase_delete", args=[self.phase.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Phase.objects.filter(pk=self.phase.id).exists())

    def test_other_trainer_gets_404_on_all_of_the_above(self):
        other_owner, other_gym, other_trainer, other_client = make_gym_trainer_client(
            "struct_owner2", "struct_trainer2", "struct_client2"
        )
        c = HttpClient()
        c.force_login(other_trainer.user)
        self.assertEqual(c.get(reverse("workout_delete", args=[self.workout.id])).status_code, 404)
        self.assertEqual(c.get(reverse("phase_edit", args=[self.phase.id])).status_code, 404)
        self.assertEqual(c.get(reverse("phase_delete", args=[self.phase.id])).status_code, 404)
        self.assertEqual(c.post(reverse("week_create", args=[self.phase.id])).status_code, 404)
        self.assertEqual(c.get(reverse("week_delete", args=[self.week.id])).status_code, 404)
