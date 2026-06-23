from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


def _apply_admin_field_labels(model, labels):
    for field_name, label in labels.items():
        try:
            model._meta.get_field(field_name).verbose_name = label
        except Exception:
            continue


_apply_admin_field_labels(User, {
    "username": "Usuario",
    "email": "Correo",
    "first_name": "Nombre",
    "last_name": "Apellidos",
    "company_code": "Código empresa",
    "contact_code": "Código contacto",
    "address_code": "Código dirección",
    "language_code": "Idioma",
    "user_type": "Tipo de usuario",
    "is_quality_admin": "Administrador de calidad",
    "is_staff": "Es personal",
    "is_active": "Activo",
    "date_joined": "Alta",
    "last_login": "Último acceso",
})


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Contexto operativo', {'fields': ('company_code', 'contact_code', 'address_code', 'language_code', 'user_type', 'is_quality_admin')}),
    )
    list_display = ('username', 'email', 'company_code', 'contact_code', 'language_code', 'user_type', 'is_staff')
