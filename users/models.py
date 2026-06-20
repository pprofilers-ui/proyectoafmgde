from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class UserType(models.TextChoices):
        INTERNAL = 'internal', 'Internal'
        CLIENT = 'client', 'Client'

    class LanguageCode(models.TextChoices):
        ESP = 'ESP', 'Espanol'
        ENG = 'ENG', 'Ingles'
        FRA = 'FRA', 'Frances'
        POR = 'POR', 'Portugues'
        ITA = 'ITA', 'Italiano'

    company_code = models.CharField(max_length=50, blank=True)
    contact_code = models.CharField(max_length=50, blank=True)
    address_code = models.CharField(max_length=50, blank=True)
    language_code = models.CharField(max_length=3, choices=LanguageCode.choices, default=LanguageCode.ESP)
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.CLIENT)
    is_quality_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.username
