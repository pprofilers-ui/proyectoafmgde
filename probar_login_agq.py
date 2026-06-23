import argparse
import base64
import json
import sys
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


DEFAULT_TIMEOUT = 30


def build_headers(api_basic: Optional[str]) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_basic:
        headers["Authorization"] = f"Basic {api_basic}"
    return headers


def encode_segment(value: str) -> str:
    return quote(value, safe="")


def call_generate_message(
    base_url: str,
    app_id: int,
    username: str,
    password: str,
    timeout: int,
    api_basic: Optional[str],
) -> Dict[str, Any]:
    url = (
        f"{base_url.rstrip('/')}/api/test/validarCredenciales/"
        f"{app_id}/{encode_segment(username)}/{encode_segment(password)}"
    )
    response = requests.get(
        url,
        headers=build_headers(api_basic),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    payload["_debug"] = {"url": url, "status_code": response.status_code}
    return payload


def call_validate_message(
    base_url: str,
    app_id: int,
    message: str,
    timeout: int,
    api_basic: Optional[str],
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/usuarios/validarCredenciales/{app_id}"
    response = requests.post(
        url,
        headers={**build_headers(api_basic), "Content-Type": "application/json"},
        json={"Message": message},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    payload["_debug"] = {"url": url, "status_code": response.status_code}
    return payload


def pretty_print(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prueba aislada del flujo AGQ validarCredenciales sin tocar la aplicación Django."
    )
    parser.add_argument("--base-url", required=True, help="URL base del servicio, por ejemplo https://api-pro-sil.agqlabs.com:44383")
    parser.add_argument("--app-id", type=int, default=6, help="Id de aplicación. Por defecto 6.")
    parser.add_argument(
        "--api-basic",
        help="Credencial Basic técnica de la API en base64, sin el prefijo 'Basic '.",
    )
    parser.add_argument("--username", required=True, help="Usuario AGQ.")
    parser.add_argument("--password", required=True, help="Password AGQ.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout en segundos.")
    parser.add_argument(
        "--message-only",
        action="store_true",
        help="Solo llama al primer servicio y muestra el Message sin validar el segundo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        pretty_print("Configuración", {
            "base_url": args.base_url,
            "app_id": args.app_id,
            "api_basic_configured": bool(args.api_basic),
            "username": args.username,
            "message_only": args.message_only,
            "timeout": args.timeout,
        })

        step_1 = call_generate_message(
            base_url=args.base_url,
            app_id=args.app_id,
            username=args.username,
            password=args.password,
            timeout=args.timeout,
            api_basic=args.api_basic,
        )
        pretty_print("Respuesta paso 1 - generar Message", step_1)

        message = step_1.get("Message")
        if not message:
            print("\nNo se recibió el campo 'Message'. No se puede continuar.")
            return 2

        if args.message_only:
            print("\nResultado final: Message obtenido correctamente.")
            return 0

        step_2 = call_validate_message(
            base_url=args.base_url,
            app_id=args.app_id,
            message=message,
            timeout=args.timeout,
            api_basic=args.api_basic,
        )
        pretty_print("Respuesta paso 2 - validar Message", step_2)

        response_value: Optional[bool] = step_2.get("Response")
        if response_value is True:
            print("\nResultado final: credenciales válidas.")
            return 0
        if response_value is False:
            print("\nResultado final: credenciales inválidas.")
            return 1

        print("\nResultado final: respuesta no reconocida. Revisa el payload devuelto.")
        return 3

    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "?"
        response_text = exc.response.text if exc.response is not None else str(exc)
        print("\nError HTTP durante la prueba:")
        print(f"Status code: {status_code}")
        print(response_text)
        return 10
    except requests.RequestException as exc:
        print("\nError de conexión durante la prueba:")
        print(str(exc))
        return 11
    except Exception as exc:
        print("\nError no controlado durante la prueba:")
        print(str(exc))
        return 12


if __name__ == "__main__":
    sys.exit(main())
