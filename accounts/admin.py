from django.contrib import admin

from .models import Client, Gym, Trainer, UserProfile


@admin.register(Gym)
class GymAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("user", "gym", "created_at")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("user", "trainer", "created_at")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "theme")
