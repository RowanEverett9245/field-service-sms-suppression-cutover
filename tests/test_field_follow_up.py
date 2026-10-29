from field_follow_up import FollowUpDecision, WorkOrderFollowUpRequest, process_follow_up


class FakeGateway:
    def __init__(self) -> None:
        self.calls = []

    def send(self, to_phone: str, message: str, idempotency_key: str) -> str:
        self.calls.append(
            {
                "to_phone": to_phone,
                "message": message,
                "idempotency_key": idempotency_key,
            }
        )
        return "msg_123"


def test_opted_out_customer_is_suppressed_without_sending() -> None:
    gateway = FakeGateway()
    request = WorkOrderFollowUpRequest(
        work_order_id="WO-77",
        customer_name="Tessa Hall",
        customer_phone="+15555550101",
        customer_opted_out=True,
        dispatch_status="completed",
        photo_count=2,
        technician_follow_up="Filter replaced and airflow restored.",
        scheduled_callback=False,
    )

    result: FollowUpDecision = process_follow_up(request, sms_gateway=gateway)

    assert result.status == "suppressed"
    assert result.reason == "customer_opted_out"
    assert gateway.calls == []


def test_completed_job_with_note_and_photos_is_queued() -> None:
    gateway = FakeGateway()
    request = WorkOrderFollowUpRequest(
        work_order_id="WO-2041",
        customer_name="Marta Ruiz",
        customer_phone="+15555550100",
        customer_opted_out=False,
        dispatch_status="completed",
        photo_count=3,
        technician_follow_up="Water heater relit and tested.",
        scheduled_callback=False,
    )

    result = process_follow_up(request, sms_gateway=gateway)

    assert result.status == "queued"
    assert result.reason == "customer_update_sent"
    assert "WO-2041" in (result.message or "")
    assert len(gateway.calls) == 1
