# AFMGDE

Proyecto Django/DRF para el modulo de gestion de estudios de estabilidad.

## Puesta en marcha

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Alcance inicial

La base del proyecto esta preparada para:
- autenticacion JWT con contexto de empresa/contacto
- Swagger
- auditoria basica
- entidades nucleares de fase 1
- capa preparada para integraciones ESB
