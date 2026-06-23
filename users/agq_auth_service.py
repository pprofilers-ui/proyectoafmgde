from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


class AgqAuthError(Exception):
    pass


@dataclass
class AgqAuthResult:
    is_valid: bool
    message: str
    generate_payload: Dict[str, Any]
    validate_payload: Dict[str, Any]


class AgqAuthService:
    def __init__(self, base_url: str, app_id: int, api_basic: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.api_basic = api_basic
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Basic {self.api_basic}",
        }

    @staticmethod
    def _encode_segment(value: str) -> str:
        return quote(value, safe="")

    def generate_message(self, username: str, password: str) -> Dict[str, Any]:
        url = (
            f"{self.base_url}/api/test/validarCredenciales/"
            f"{self.app_id}/{self._encode_segment(username)}/{self._encode_segment(password)}"
        )
        response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text.strip() if response.text else str(exc)
            raise AgqAuthError(f"Error HTTP en generate_message: {response.status_code} {detail}") from exc

        payload = response.json()
        payload["_debug"] = {"url": url, "status_code": response.status_code}
        return payload

    def validate_message(self, message: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/usuarios/validarCredenciales/{self.app_id}"
        response = requests.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"Message": message},
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text.strip() if response.text else str(exc)
            raise AgqAuthError(f"Error HTTP en validate_message: {response.status_code} {detail}") from exc

        payload = response.json()
        payload["_debug"] = {"url": url, "status_code": response.status_code}
        return payload

    def authenticate(self, username: str, password: str) -> AgqAuthResult:
        generate_payload = self.generate_message(username=username, password=password)
        message: Optional[str] = generate_payload.get("Message")
        if not message:
            raise AgqAuthError("La respuesta del primer servicio no contiene 'Message'.")

        validate_payload = self.validate_message(message=message)
        response_value = validate_payload.get("Response")
        if not isinstance(response_value, bool):
            raise AgqAuthError("La respuesta del segundo servicio no contiene un booleano válido en 'Response'.")

        return AgqAuthResult(
            is_valid=response_value,
            message=message,
            generate_payload=generate_payload,
            validate_payload=validate_payload,
        )
