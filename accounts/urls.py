from django.urls import path

from . import views

urlpatterns = [
    path("accounts/profile/", views.profile, name="profile"),
    path("accounts/theme/", views.set_theme, name="set_theme"),
    path("post-login/", views.post_login_redirect, name="post_login_redirect"),

    path("owner/", views.owner_dashboard, name="owner_dashboard"),
    path("owner/trainers/new/", views.trainer_create, name="owner_trainer_create"),

    path("trainer/", views.trainer_dashboard, name="trainer_dashboard"),
    path("trainer/clients/new/", views.client_create, name="trainer_client_create"),
    path("trainer/clients/<int:client_id>/", views.client_detail, name="trainer_client_detail"),

    path("client/", views.client_dashboard, name="client_dashboard"),
]
