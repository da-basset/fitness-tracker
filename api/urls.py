from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import manage, views

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="api_token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="api_logout"),
    path("me/", views.MeView.as_view(), name="api_me"),
    path("plans/active/", views.ActivePlanView.as_view(), name="api_active_plan"),
    path("plans/active/schedule/", views.ActiveScheduleView.as_view(), name="api_active_schedule"),
    path("workouts/<int:workout_id>/", views.WorkoutView.as_view(), name="api_workout"),
    path(
        "exercises/<int:exercise_id>/sets/<int:set_number>/completion/",
        views.SetCompletionView.as_view(),
        name="api_set_completion",
    ),
    path(
        "weeks/<int:week_id>/workouts/<int:workout_id>/completion/",
        views.WorkoutCompletionView.as_view(),
        name="api_workout_completion",
    ),
    path("history/", views.HistoryView.as_view(), name="api_history"),
    path("sync/", views.SyncView.as_view(), name="api_sync"),
    # Trainer/owner management (see api/manage.py).
    path("trainers/", manage.TrainerListView.as_view(), name="api_trainers"),
    path("trainers/<int:trainer_id>/plans/", manage.PlanLibraryView.as_view(), name="api_plan_library"),
    path("clients/", manage.ClientListView.as_view(), name="api_clients"),
    path("clients/<int:client_id>/", manage.ClientDetailView.as_view(), name="api_client_detail"),
    path("plans/<int:plan_id>/", manage.PlanDetailView.as_view(), name="api_plan_detail"),
    path("plans/<int:plan_id>/assign/", manage.PlanAssignView.as_view(), name="api_plan_assign"),
    path("assignments/<int:assignment_id>/unassign/", manage.UnassignView.as_view(), name="api_unassign"),
    path("plans/<int:plan_id>/workouts/", manage.WorkoutCreateView.as_view(), name="api_plan_workouts"),
    path("plans/<int:plan_id>/workouts/<int:workout_id>/", manage.WorkoutEditView.as_view(), name="api_plan_workout_edit"),
    path(
        "plans/<int:plan_id>/workouts/<int:workout_id>/exercises/",
        manage.ExerciseCreateView.as_view(),
        name="api_plan_exercises",
    ),
    path(
        "plans/<int:plan_id>/workouts/<int:workout_id>/exercises/reorder/",
        manage.ExerciseReorderView.as_view(),
        name="api_plan_exercises_reorder",
    ),
    path("plans/<int:plan_id>/exercises/<int:exercise_id>/", manage.ExerciseEditView.as_view(), name="api_plan_exercise_edit"),
    path("plans/<int:plan_id>/phases/", manage.PhaseCreateView.as_view(), name="api_plan_phases"),
    path("plans/<int:plan_id>/phases/<int:phase_id>/", manage.PhaseEditView.as_view(), name="api_plan_phase_edit"),
    path("plans/<int:plan_id>/phases/<int:phase_id>/weeks/", manage.WeekCreateView.as_view(), name="api_plan_weeks"),
    path("plans/<int:plan_id>/weeks/<int:week_id>/", manage.WeekEditView.as_view(), name="api_plan_week_edit"),
    path("plans/<int:plan_id>/nutrients/", manage.NutrientCreateView.as_view(), name="api_plan_nutrients"),
    path("plans/<int:plan_id>/nutrients/<int:nutrient_id>/", manage.NutrientEditView.as_view(), name="api_plan_nutrient_edit"),
    path("plans/<int:plan_id>/supplements/", manage.SupplementCreateView.as_view(), name="api_plan_supplements"),
    path(
        "plans/<int:plan_id>/supplements/<int:supplement_id>/",
        manage.SupplementEditView.as_view(),
        name="api_plan_supplement_edit",
    ),
    path("schema/", SpectacularAPIView.as_view(permission_classes=[]), name="api_schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api_schema", permission_classes=[]), name="api_docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api_schema", permission_classes=[]), name="api_redoc"),
]
