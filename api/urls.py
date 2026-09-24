from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

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
    path("schema/", SpectacularAPIView.as_view(permission_classes=[]), name="api_schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api_schema", permission_classes=[]), name="api_docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api_schema", permission_classes=[]), name="api_redoc"),
]
