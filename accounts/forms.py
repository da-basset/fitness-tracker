from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class AccountCreateForm(UserCreationForm):
    """Creates a login for a new Trainer or Client (the view decides which
    profile to attach). Reuses Django's built-in username/password
    validation (uniqueness, password strength, confirmation) -- the view
    is responsible for creating the Trainer/Client profile itself once
    this User is saved. Collects first/last name too, so client cards on
    /trainer have a real name to show instead of always falling back to
    the username."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
