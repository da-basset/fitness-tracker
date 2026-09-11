from django.urls import path

from . import views

urlpatterns = [
    path("", views.hub, name="training_hub"),
    path("physical/", views.physical, name="training_physical"),
    path("spanish/", views.spanish, name="training_spanish"),
    path("reading/", views.reading, name="training_reading"),

    # Client's own live schedule + today's tracking.
    path("api/schedule/", views.api_schedule, name="training_api_schedule"),
    path("api/workouts/<int:workout_id>/", views.api_workout, name="training_api_workout"),
    path(
        "api/exercises/<int:exercise_id>/sets/<int:set_number>/toggle/",
        views.api_toggle_set,
        name="training_api_toggle_set",
    ),
    path(
        "api/workouts/<int:workout_id>/complete/",
        views.api_toggle_workout_complete,
        name="training_api_toggle_workout_complete",
    ),

    # Trainer/Owner plan library (templates) + clone-on-assign.
    path("trainers/<int:trainer_id>/plans/", views.plan_library, name="plan_library"),
    path("trainers/<int:trainer_id>/plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:plan_id>/delete/", views.plan_delete, name="plan_delete"),
    path("plans/<int:plan_id>/assign/", views.plan_assign, name="plan_assign"),
    path("assignments/<int:assignment_id>/unassign/", views.plan_unassign, name="plan_unassign"),
    path("assignments/<int:assignment_id>/", views.client_plan_history, name="client_plan_history"),

    # Trainer/Owner: one plan's live schedule/exercise editor + read-only preview.
    path("plans/<int:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/<int:plan_id>/preview/", views.plan_preview, name="plan_preview"),
    path("plans/<int:plan_id>/api/schedule/", views.api_plan_schedule, name="api_plan_schedule"),
    path("plans/<int:plan_id>/api/workouts/<int:workout_id>/", views.api_plan_workout, name="api_plan_workout"),
    path(
        "plans/<int:plan_id>/api/workouts/<int:workout_id>/exercises/",
        views.api_plan_create_exercise,
        name="api_plan_create_exercise",
    ),
    path(
        "plans/<int:plan_id>/api/workouts/<int:workout_id>/exercises/reorder/",
        views.api_plan_reorder_exercises,
        name="api_plan_reorder_exercises",
    ),
    path(
        "plans/<int:plan_id>/api/exercises/<int:exercise_id>/",
        views.api_plan_exercise_detail,
        name="api_plan_exercise_detail",
    ),

    # Trainer/Owner: Nutrients & Supplements reference lists, plan-scoped.
    path("plans/<int:plan_id>/manage/nutrients/new/", views.plan_nutrient_create, name="plan_nutrient_create"),
    path("manage/nutrients/<int:nutrient_id>/", views.nutrient_edit, name="nutrient_edit"),
    path("manage/nutrients/<int:nutrient_id>/delete/", views.nutrient_delete, name="nutrient_delete"),
    path("plans/<int:plan_id>/manage/supplements/new/", views.plan_supplement_create, name="plan_supplement_create"),
    path("manage/supplements/<int:supplement_id>/", views.supplement_edit, name="supplement_edit"),
    path("manage/supplements/<int:supplement_id>/delete/", views.supplement_delete, name="supplement_delete"),

    # Trainer/Owner: Workouts & Phases structural editor, plan-scoped.
    path("plans/<int:plan_id>/manage/", views.plan_manage, name="plan_manage"),
    path("plans/<int:plan_id>/manage/workouts/new/", views.plan_workout_create, name="plan_workout_create"),
    path("manage/workouts/<int:workout_id>/", views.workout_edit, name="workout_edit"),
    path("manage/workouts/<int:workout_id>/delete/", views.workout_delete, name="workout_delete"),
    path("plans/<int:plan_id>/manage/phases/new/", views.plan_phase_create, name="plan_phase_create"),
    path("manage/phases/<int:phase_id>/", views.phase_edit, name="phase_edit"),
    path("manage/phases/<int:phase_id>/delete/", views.phase_delete, name="phase_delete"),
    path("manage/phases/<int:phase_id>/weeks/new/", views.week_create, name="week_create"),
    path("manage/weeks/<int:week_id>/delete/", views.week_delete, name="week_delete"),
]
