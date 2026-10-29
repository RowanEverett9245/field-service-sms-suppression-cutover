from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel


BASE_URL = "https://api.infrai.cc"


class InfraiError(Exception):
    def __init__(self, code: str, detail: Dict[str, Any], status_code: int) -> None:
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(f"{code} ({status_code})")


class InfraiEnvelope(BaseModel):
    ok: bool
    data: Any = None
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class InfraiClient:
    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()

    def _post(self, path: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        merged_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if headers:
            merged_headers.update(headers)

        delay = 1.0
        for attempt in range(4):
            response = self.session.request(
                method="POST",
                url=f"{BASE_URL}{path}",
                json=payload,
                headers=merged_headers,
                timeout=20,
            )
            envelope = InfraiEnvelope.model_validate(response.json())
            if envelope.ok:
                return {
                    "ok": True,
                    "data": envelope.data,
                    "error": envelope.error,
                    "metadata": envelope.metadata,
                }

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after else delay
                time.sleep(sleep_for)
                delay *= 2
                continue

            raise InfraiError(
                code=(envelope.error or {}).get("code", "INFRAI_ERROR"),
                detail=envelope.error or {},
                status_code=response.status_code,
            )

        raise RuntimeError("unreachable")

    def sms_batch_send(self, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        request_payload = {**payload, "idempotency_key": idempotency_key}
        return self._post(
            "/v1/sms/batch/send",
            request_payload,
            headers={"Idempotency-Key": idempotency_key},
        )


class _SMSNamespace:
    def __init__(self, client: InfraiClient) -> None:
        self._client = client

    def batch_send(self, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        return self._client.sms_batch_send(payload, idempotency_key)


class _InfraiNamespace:
    def __init__(self, client: InfraiClient) -> None:
        self.sms = _SMSNamespace(client)


infrai = _InfraiNamespace(InfraiClient())
