from django.conf import settings
from django.db import models


class Gym(models.Model):
    """A gym / training business. Owned by exactly one User, who has the
    ability to create Trainers under this gym."""

    name = models.CharField(max_length=150)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_gyms"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Trainer(models.Model):
    """A trainer profile for a User, scoped to exactly one Gym. Trainers
    build Plans (see training.models.Plan) and manage their own Clients."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trainer_profile"
    )
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="trainers")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.gym})"


class Client(models.Model):
    """A client profile for a User, scoped to exactly one Trainer. Clients
    get Plans assigned to them (see training.models.PlanAssignment) and log
    their own workout completions against those plans."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_profile"
    )
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name="clients")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} (trainer: {self.trainer.user})"

    @property
    def gym(self):
        return self.trainer.gym


class UserProfile(models.Model):
    """Lightweight per-user settings that apply regardless of role (Owner,
    Trainer, or Client) -- today just the site theme preference. Created
    lazily (get_or_create) the first time it's needed rather than backfilled
    for every existing user, since a missing profile just means "use the
    default"."""

    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_CHOICES = [
        (THEME_LIGHT, "Light"),
        (THEME_DARK, "Dark"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default=THEME_LIGHT)

    def __str__(self):
        return f"{self.user}'s profile"
