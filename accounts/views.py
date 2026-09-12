from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from training.models import Plan, PlanAssignment, WorkoutCompletion

from .forms import AccountCreateForm
from .models import Client, Gym, Trainer, UserProfile
from .permissions import can_manage_trainer


def _get_owned_gym(request):
    """Resolve the Gym the requesting user owns, or 404. This is the
    permission boundary for every Owner-only view -- only request.user ==
    gym.owner ever gets past it."""
    return get_object_or_404(Gym, owner=request.user)


def _get_trainer(request):
    """Resolve the requesting user's Trainer profile, or 404."""
    return get_object_or_404(Trainer, user=request.user)


def _require_manage_trainer(request, trainer):
    if not can_manage_trainer(request.user, trainer):
        raise Http404("You don't have access to this trainer.")


def _display_name(user):
    return user.get_full_name() or user.username


@login_required
def post_login_redirect(request):
    """LOGIN_REDIRECT_URL target -- sends each account type straight to its
    own landing page instead of the generic Training hub: an Owner lands on
    /owner/ (every trainer at their gym), a Trainer lands on /trainer/
    (every client assigned to them). Anyone else (a Client, or an account
    with no gym/trainer role at all) keeps landing on the Training hub,
    which is already their normal page."""
    if request.user.owned_gyms.exists():
        return redirect("owner_dashboard")
    if hasattr(request.user, "trainer_profile"):
        return redirect("trainer_dashboard")
    return redirect("training_hub")


@login_required
def owner_dashboard(request):
    """Manage trainer accounts for the gym you own -- who sees each
    trainer's own clients (and, for you, every trainer's) moved to
    /trainer, so this page is just account management now."""
    gym = _get_owned_gym(request)
    trainers = gym.trainers.select_related("user").order_by("user__username")
    return render(request, "accounts/owner_dashboard.html", {
        "gym": gym,
        "trainers": trainers,
        "owner_current": True,
    })


@login_required
def trainer_create(request):
    gym = _get_owned_gym(request)
    if request.method == "POST":
        form = AccountCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            Trainer.objects.create(user=user, gym=gym)
            return redirect("owner_dashboard")
    else:
        form = AccountCreateForm()
    return render(request, "accounts/trainer_form.html", {"form": form, "gym": gym})


@login_required
def trainer_dashboard(request):
    """Repurposed `/trainer`: a Trainer sees only their own clients; the
    Gym Owner additionally sees every trainer at their gym and each of
    their clients, inline on this same page (no further drill-down). Every
    client renders as a card linking to trainer_client_detail, which is
    where all plan/workout/phase/exercise editing happens."""
    owned_gym = Gym.objects.filter(owner=request.user).first()
    viewer_trainer = Trainer.objects.filter(user=request.user).select_related("gym").first()

    if owned_gym is not None:
        trainers = list(
            Trainer.objects.filter(gym=owned_gym).select_related("user").order_by("user__username")
        )
    elif viewer_trainer is not None:
        trainers = [viewer_trainer]
    else:
        raise Http404("You don't have access to this page.")

    sections = []
    for trainer in trainers:
        clients = trainer.clients.select_related("user").order_by("user__username")
        cards = []
        for client in clients:
            assignment = PlanAssignment.objects.filter(client=client, is_active=True).select_related("plan").first()
            cards.append({
                "client": client,
                "name": _display_name(client.user),
                "plan_name": assignment.plan.name if assignment else None,
            })
        sections.append({
            "trainer": trainer,
            "is_self": trainer.user_id == request.user.id,
            "cards": cards,
        })

    return render(request, "accounts/trainer_dashboard.html", {
        "sections": sections,
        "is_owner_view": owned_gym is not None,
        "trainer_current": True,
    })


@login_required
def client_create(request):
    trainer = _get_trainer(request)
    if request.method == "POST":
        form = AccountCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            Client.objects.create(user=user, trainer=trainer)
            return redirect("trainer_dashboard")
    else:
        form = AccountCreateForm()
    return render(request, "accounts/client_form.html", {"form": form, "trainer": trainer})


@login_required
def client_detail(request, client_id):
    """The target of every client card on /trainer: a trainer/owner's view
    of one client -- basic account info (view-only -- editing a profile is
    the user's own business, never a trainer's or owner's), simple stats,
    the active plan with links to full edit and the read-only "Client
    view", a way to assign a plan from the trainer's library, and a
    read-only list of past plans."""
    client = get_object_or_404(Client, pk=client_id)
    _require_manage_trainer(request, client.trainer)

    active_assignment = (
        PlanAssignment.objects.filter(client=client, is_active=True).select_related("plan").first()
    )
    past_assignments = (
        PlanAssignment.objects.filter(client=client, is_active=False)
        .select_related("plan")
        .order_by("-assigned_at")
    )

    stats = None
    if active_assignment is not None:
        completions = WorkoutCompletion.objects.filter(client=client, workout__plan=active_assignment.plan)
        stats = {
            "all_time_completed": completions.count(),
            "last_completed_at": completions.order_by("-log_date").values_list("log_date", flat=True).first(),
        }

    templates = Plan.objects.filter(trainer=client.trainer, assignments__isnull=True).distinct()

    return render(request, "accounts/client_detail.html", {
        "client": client,
        "active_assignment": active_assignment,
        "past_assignments": past_assignments,
        "stats": stats,
        "templates": templates,
    })


@login_required
def client_dashboard(request):
    """`/client/`: a client's own page -- their basic info, current plan
    (linking into the live, interactive Physical Training experience),
    and a read-only list of past plans. Nobody but the user themselves can
    edit their own profile from here or anywhere else."""
    client = get_object_or_404(Client, user=request.user)
    assignments = (
        client.plan_assignments.select_related("plan", "plan__trainer__user").order_by("-assigned_at")
    )
    active_assignment = next((a for a in assignments if a.is_active), None)
    past_assignments = [a for a in assignments if not a.is_active]

    return render(request, "accounts/client_dashboard.html", {
        "client": client,
        "active_assignment": active_assignment,
        "past_assignments": past_assignments,
        "client_current": True,
    })


@login_required
def profile(request):
    """A user's own profile page: their account info plus whichever
    role(s) they hold (Owner / Trainer / Client -- a user can be more than
    one, as Isaac himself is). Linked from the settings panel in
    base.html. Read-only for now -- editing is a later pass, and even
    then, only the user themselves will ever get an edit control here."""
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    owned_gym = Gym.objects.filter(owner=user).first()
    trainer_profile = Trainer.objects.filter(user=user).select_related("gym").first()
    client_profile = Client.objects.filter(user=user).select_related("trainer__user").first()

    return render(request, "accounts/profile.html", {
        "profile": profile,
        "owned_gym": owned_gym,
        "trainer_profile": trainer_profile,
        "client_profile": client_profile,
    })


@login_required
@require_http_methods(["POST"])
def set_theme(request):
    """Persists the requesting user's dark/light mode choice so it follows
    them across devices/browsers, instead of living only in that one
    browser's localStorage. Called by main.js whenever the dark-mode
    toggle in the settings panel changes; anonymous visitors never hit
    this (the toggle still works for them via localStorage alone)."""
    theme = request.POST.get("theme")
    valid_themes = {choice for choice, _ in UserProfile.THEME_CHOICES}
    if theme not in valid_themes:
        return JsonResponse({"error": "invalid theme"}, status=400)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.theme = theme
    profile.save(update_fields=["theme"])
    return JsonResponse({"theme": profile.theme})
