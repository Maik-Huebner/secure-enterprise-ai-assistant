"""Thin HTTP client for the NovaBank API, used by the Gradio interface."""

from __future__ import annotations

from typing import Any

import httpx


class ApiError(Exception):
    """API failure with a German message that is safe to show to the user."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ApiClient:
    """Calls the REST API. ``http`` can be a FastAPI TestClient in tests."""

    def __init__(self, base_url: str, http: Any = None, timeout: float = 300) -> None:
        # Any object with httpx.Client's request() works, e.g. FastAPI's TestClient in tests.
        self._http: Any = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def _request(self, method: str, path: str, token: str | None = None, **kwargs: Any) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError("Die API ist nicht erreichbar. Läuft `novabank-api`?") from exc
        if response.status_code == 401 and token:
            raise ApiError("Die Sitzung ist abgelaufen. Bitte erneut anmelden.", 401)
        if response.is_error:
            try:
                detail = str(response.json().get("detail", ""))
            except ValueError:
                detail = ""
            raise ApiError(
                detail or f"Die API meldet Fehler {response.status_code}.", response.status_code
            )
        return response.json()

    def login(self, username: str, password: str) -> str:
        payload = self._request(
            "POST", "/v1/auth/token", json={"username": username, "password": password}
        )
        return str(payload["access_token"])

    def me(self, token: str) -> dict[str, Any]:
        return dict(self._request("GET", "/v1/me", token))

    def cases(self, token: str) -> list[dict[str, Any]]:
        return list(self._request("GET", "/v1/cases", token))

    def case(self, token: str, case_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/v1/cases/{case_id}", token))

    def chat(self, token: str, message: str) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/chat", token, json={"message": message}))

    def reviews(self, token: str) -> list[dict[str, Any]]:
        return list(self._request("GET", "/v1/reviews", token))

    def review(self, token: str, thread_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/v1/reviews/{thread_id}", token))

    def decide(self, token: str, thread_id: str, decision: str, comment: str) -> dict[str, Any]:
        return dict(
            self._request(
                "POST",
                f"/v1/reviews/{thread_id}",
                token,
                json={"decision": decision, "comment": comment},
            )
        )

    def ready(self) -> dict[str, Any]:
        return dict(self._request("GET", "/ready"))
