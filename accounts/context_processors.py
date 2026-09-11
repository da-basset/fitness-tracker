from .models import UserProfile


def user_theme(request):
    """Exposes the logged-in user's saved theme to every template (base.html
    needs it on every page, since the settings panel/dark-mode toggle lives
    there). Anonymous visitors get None -- main.js falls back to
    localStorage/OS preference for them, same as before this feature."""
    if not request.user.is_authenticated:
        return {"user_theme": None}

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return {"user_theme": profile.theme}
