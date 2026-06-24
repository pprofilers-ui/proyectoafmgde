import os

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from stability.models import Client, Study  # noqa: E402


CLIENTS = [
    {
        "code": "CLI-AGQ-001",
        "description": "AGQ Labs - Estabilidad Interna",
        "address": "Parque Tecnologico, Sevilla",
        "email": "stability@agqlabs.com",
        "phone": "+34 900 100 200",
        "notes": "Cliente principal para pruebas de estabilidad internas.",
    },
    {
        "code": "CLI-BES-002",
        "description": "Besafer Pharma",
        "address": "Madrid, Spain",
        "email": "qa@besaferpharma.com",
        "phone": "+34 910 200 300",
        "notes": "Cliente de ejemplo para estudios de larga duración.",
    },
    {
        "code": "CLI-NET-003",
        "description": "Netpharmalab",
        "address": "Barcelona, Spain",
        "email": "contacto@netpharmalab.com",
        "phone": "+34 930 400 500",
        "notes": "Cliente de prueba para validaciones de flujo completo.",
    },
]


STUDY_CLIENT_MAP = {
    "EST-001": "CLI-AGQ-001",
    "EST-002": "CLI-BES-002",
    "EST-2026-003": "CLI-NET-003",
    "EST-2026-004": "CLI-AGQ-001",
    "EST-2026-005": "CLI-BES-002",
    "EST-2026-006": "CLI-NET-003",
    "EST-2026-007": "CLI-AGQ-001",
    "EST-2026-008": "CLI-BES-002",
}


def seed_clients():
    created = []
    for payload in CLIENTS:
        client, _ = Client.objects.update_or_create(
            code=payload["code"],
            defaults=payload,
        )
        created.append(client)
    return created


def link_studies_to_clients():
    linked = []
    clients = {client.code: client for client in Client.objects.all()}
    for study_code, client_code in STUDY_CLIENT_MAP.items():
        study = Study.objects.filter(code=study_code).first()
        client = clients.get(client_code)
        if not study or not client:
            continue
        study.client = client
        study.save(update_fields=["client", "updated_at"])
        linked.append((study.code, client.code))
    return linked


if __name__ == "__main__":
    clients = seed_clients()
    linked = link_studies_to_clients()
    print(f"Clientes creados/actualizados: {len(clients)}")
    print(f"Estudios enlazados: {len(linked)}")
    for study_code, client_code in linked:
        print(f" - {study_code} -> {client_code}")
