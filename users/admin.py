from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Operational context', {'fields': ('company_code', 'contact_code', 'address_code', 'language_code', 'user_type', 'is_quality_admin')}),
    )
    list_display = ('username', 'email', 'company_code', 'contact_code', 'language_code', 'user_type', 'is_staff')
