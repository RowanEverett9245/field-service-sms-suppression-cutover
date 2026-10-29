from __future__ import annotations

import hashlib
import os
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from infrai_client import infrai


SendStatus = Literal["queued", "suppressed"]
DispatchStatus = Literal["scheduled", "en_route", "completed", "cancelled"]


class WorkOrderFollowUpRequest(BaseModel):
    work_order_id: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    customer_phone: str = Field(min_length=8)
    customer_opted_out: bool
    dispatch_status: DispatchStatus
    photo_count: int = Field(ge=0)
    technician_follow_up: str = Field(default="")
    scheduled_callback: bool = False


class FollowUpDecision(BaseModel):
    status: SendStatus
    reason: str
    message: str | None = None
    provider_message_id: str | None = None


class SMSGateway(Protocol):
    def send(self, to_phone: str, message: str, idempotency_key: str) -> str:
        ...


class InfraiSMSGateway:
    def send(self, to_phone: str, message: str, idempotency_key: str) -> str:
        sender = os.environ.get("SMS_FROM", "FieldOps")
        result = infrai.sms.batch.send(
            {
                "messages": [
                    {
                        "to": to_phone,
                        "from": sender,
                        "message": message,
                    }
                ]
            },
            idempotency_key=idempotency_key,
        )
        data = result["data"]
        if isinstance(data, dict) and "items" in data and data["items"]:
            first_item = data["items"][0]
            if isinstance(first_item, dict) and "message_id" in first_item:
                return str(first_item["message_id"])
        if isinstance(data, dict) and "message_id" in data:
            return str(data["message_id"])
        return "queued"


SENDABLE_STATUSES = {"en_route", "completed"}


def build_customer_message(request: WorkOrderFollowUpRequest) -> str:
    note = request.technician_follow_up.strip()
    parts = [f"Work order {request.work_order_id} {request.dispatch_status.replace('_', ' ')}."]
    if note:
        parts.append(f"Technician note: {note}")
    if request.photo_count > 0:
        parts.append(f"{request.photo_count} photo(s) attached to the job record.")
    if request.scheduled_callback:
        parts.append("A callback has been scheduled.")
    return " ".join(parts)


def follow_up_idempotency_key(request: WorkOrderFollowUpRequest) -> str:
    raw = "|".join(
        [
            request.work_order_id,
            request.customer_phone,
            request.dispatch_status,
            str(request.photo_count),
            request.technician_follow_up.strip(),
            str(request.scheduled_callback),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"work-order-follow-up:{digest}"


def process_follow_up(request: WorkOrderFollowUpRequest, sms_gateway: SMSGateway) -> FollowUpDecision:
    if request.customer_opted_out:
        return FollowUpDecision(status="suppressed", reason="customer_opted_out")

    if request.dispatch_status not in SENDABLE_STATUSES:
        return FollowUpDecision(status="suppressed", reason="dispatch_status_not_sendable")

    has_note = bool(request.technician_follow_up.strip())
    has_photos = request.photo_count > 0
    if not has_note and not has_photos and not request.scheduled_callback:
        return FollowUpDecision(status="suppressed", reason="no_customer_relevant_update")

    message = build_customer_message(request)
    provider_message_id = sms_gateway.send(
        to_phone=request.customer_phone,
        message=message,
        idempotency_key=follow_up_idempotency_key(request),
    )
    return FollowUpDecision(
        status="queued",
        reason="customer_update_sent",
        message=message,
        provider_message_id=provider_message_id,
    )
