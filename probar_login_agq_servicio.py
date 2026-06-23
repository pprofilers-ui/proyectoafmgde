import argparse
import json
import sys

from users.agq_auth_service import AgqAuthError, AgqAuthService


def pretty_print(title, payload):
    print(f"\n=== {title} ===")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prueba el servicio AGQ desde el código interno de AFMGDE sin tocar el login actual."
    )
    parser.add_argument("--base-url", required=True, help="URL base del servicio AGQ.")
    parser.add_argument("--app-id", type=int, default=6, help="Id de aplicación. Por defecto 6.")
    parser.add_argument("--api-basic", required=True, help="Basic técnico de la API, sin el prefijo 'Basic '.")
    parser.add_argument("--username", required=True, help="Usuario AGQ.")
    parser.add_argument("--password", required=True, help="Password AGQ.")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout en segundos.")
    return parser.parse_args()


def main():
    args = parse_args()

    service = AgqAuthService(
        base_url=args.base_url,
        app_id=args.app_id,
        api_basic=args.api_basic,
        timeout=args.timeout,
    )

    try:
        pretty_print("Configuración", {
            "base_url": args.base_url,
            "app_id": args.app_id,
            "username": args.username,
            "timeout": args.timeout,
            "uses_internal_service_class": True,
        })
        result = service.authenticate(username=args.username, password=args.password)
        pretty_print("Respuesta paso 1 - generar Message", result.generate_payload)
        pretty_print("Respuesta paso 2 - validar Message", result.validate_payload)
        if result.is_valid:
            print("\nResultado final: credenciales válidas.")
            return 0
        print("\nResultado final: credenciales inválidas.")
        return 1
    except AgqAuthError as exc:
        print("\nError funcional del servicio AGQ:")
        print(str(exc))
        return 2
    except Exception as exc:
        print("\nError no controlado:")
        print(str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main())
