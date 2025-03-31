from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User  # Import your custom User model

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("username", "email", "role", "is_staff", "is_superuser", "joined_date")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email")}),
        ("Roles", {"fields": ("role",)}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
        ("Important Dates", {"fields": ("last_login",)}),  # Remove `joined_date` from here
    )
    readonly_fields = ("joined_date",)  # Mark `joined_date` as read-only
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "role", "password1", "password2"),
        }),
    )
    search_fields = ("username", "email")
    ordering = ("username",)

# Register the custom User model
admin.site.register(User, CustomUserAdmin)

