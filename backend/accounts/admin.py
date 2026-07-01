"""Admin Django : User personnalisé (avec le champ `role`) + Profile."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Réutilise l'admin User standard de Django en exposant le rôle EduTutor."""

    list_display = ("username", "email", "role", "is_staff", "is_active", "date_joined")
    list_filter = DjangoUserAdmin.list_filter + ("role",)
    fieldsets = DjangoUserAdmin.fieldsets + (("Rôle EduTutor", {"fields": ("role",)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Rôle EduTutor", {"fields": ("role",)}),)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_verified", "created_at")
    list_filter = ("email_verified",)
    search_fields = ("user__username", "user__email")
