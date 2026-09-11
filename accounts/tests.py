"""Tests for the role-aware post-login landing page redirect. Uses its own
fixtures rather than depending on real data, so this suite is safe to run
against the throwaway test database `manage.py test` always creates."""

from django.contrib.auth import get_user_model
from django.test import Client as HttpClient
from django.test import TestCase
from django.urls import reverse

from accounts.models import Client as ClientProfile
from accounts.models import Gym, Trainer

User = get_user_model()


class PostLoginRedirectTests(TestCase):
    """LOGIN_REDIRECT_URL points at this view: an Owner should land on
    their "all my trainers" page, a Trainer on their "all my clients"
    page, and everyone else (a Client, or a bare account with no gym/
    trainer role) on the Training hub, unchanged from before."""

    def setUp(self):
        self.owner = User.objects.create_user("owner5", password="pw")
        self.gym = Gym.objects.create(name="Owner5's Gym", owner=self.owner)
        trainer_user = User.objects.create_user("trainer5", password="pw")
        self.trainer = Trainer.objects.create(user=trainer_user, gym=self.gym)
        client_user = User.objects.create_user("client5", password="pw")
        self.client_profile = ClientProfile.objects.create(user=client_user, trainer=self.trainer)
        self.plain_user = User.objects.create_user("plain5", password="pw")

    def login(self, username):
        c = HttpClient()
        c.force_login(User.objects.get(username=username))
        return c

    def test_owner_lands_on_owner_dashboard(self):
        c = self.login("owner5")
        resp = c.get(reverse("post_login_redirect"))
        self.assertRedirects(resp, reverse("owner_dashboard"))

    def test_trainer_lands_on_trainer_dashboard(self):
        c = self.login("trainer5")
        resp = c.get(reverse("post_login_redirect"))
        self.assertRedirects(resp, reverse("trainer_dashboard"))

    def test_client_lands_on_training_hub(self):
        c = self.login("client5")
        resp = c.get(reverse("post_login_redirect"))
        self.assertRedirects(resp, reverse("training_hub"))

    def test_plain_account_lands_on_training_hub(self):
        c = self.login("plain5")
        resp = c.get(reverse("post_login_redirect"))
        self.assertRedirects(resp, reverse("training_hub"))

    def test_login_view_is_wired_to_post_login_redirect(self):
        """LOGIN_REDIRECT_URL is actually this view -- logging in sends you
        here first, which then (per the tests above) sends an Owner on to
        /owner/. assertRedirects can't follow a redirect-to-a-redirect in
        one call, so this just confirms the first hop."""
        c = HttpClient()
        resp = c.post(reverse("login"), {"username": "owner5", "password": "pw"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("post_login_redirect"))
