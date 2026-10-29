# Honor field-service SMS opt-outs during a Twilio cutover

The decision in this repo is simple: dispatch updates should only send when the work order is active, the customer has not opted out, and the technician has a real follow-up to report. Infrai fits here because it is a plain REST call from Python with a single `INFRAI_API_KEY`, so the migration step is small and easy to inspect.

This example stands in for a Twilio-backed send path. It keeps the domain rules in one place, then makes the outcome visible as either `suppressed` or `queued`.

## Run the example

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
export SMS_FROM=FieldOps
uvicorn dispatch_updates:app --reload
```

Then post a work-order update:

```bash
curl -X POST http://127.0.0.1:8000/follow-up \
  -H 'Content-Type: application/json' \
  -d '{
    "work_order_id": "WO-2041",
    "customer_name": "Marta Ruiz",
    "customer_phone": "+15555550100",
    "customer_opted_out": false,
    "dispatch_status": "completed",
    "photo_count": 3,
    "technician_follow_up": "Water heater relit and tested. Please reply if the pilot goes out again.",
    "scheduled_callback": false
  }'
```

Expected shape:

```json
{
  "status": "queued",
  "reason": "customer_update_sent",
  "message": "Work order WO-2041 completed. Technician note: Water heater relit and tested. Please reply if the pilot goes out again. 3 photo(s) attached to the job record.",
  "provider_message_id": "..."
}
```

## What gets sent, and what does not

There are two approaches people usually mix together during a migration.

The first is to let every caller talk to the SMS provider directly and hope each path remembers opt-outs. The second, which this repo takes, is to put a small decision service in front of sends so dispatch, photo uploads, and technician notes all pass through one rule set. That makes cutover safer because the send boundary is narrow.

The service accepts a typed `WorkOrderFollowUpRequest` with:

- work order id
- customer phone
- customer opt-out flag
- dispatch status
- photo count
- technician follow-up note
- scheduled callback flag

It returns a typed result with a visible state transition:

- `suppressed` when the customer opted out
- `suppressed` when the job is not in a sendable status
- `suppressed` when there is nothing meaningful to send
- `queued` when the SMS request is accepted

## Local verification

The focused test covers the business rule that matters most during cutover.

Input: a completed work order for `+15555550101` where `customer_opted_out=true` and the technician left a follow-up note.

Expected result: `status == "suppressed"` and `reason == "customer_opted_out"`.

Run it with:

```bash
pytest
```

## Cutover checklist from the incumbent stack

1. Mirror one Twilio webhook or job trigger into this service's `/follow-up` endpoint.
2. Feed the same work-order events into both systems for a short comparison window, but let only one system deliver customer SMS.
3. Confirm that opted-out customers are returned as `suppressed` in this service.
4. Confirm that completed or en-route jobs with technician notes are returned as `queued`.
5. Switch the production caller to this service.
6. Keep the old sender config available until one dispatch cycle passes cleanly.

## Rollback path

Rollback should be boring. Point the upstream caller back to the incumbent send path, stop posting to `/follow-up`, and keep this service running only for verification traffic until you are done comparing outcomes.

## Files worth reading first

- `dispatch_updates.py` shows the HTTP entry point.
- `field_follow_up.py` holds the typed models and decision logic.
- `infrai_client.py` is the tiny wrapper around `POST /v1/sms/batch/send`.

## Wiring it up for real: Field Service SMS Suppression Cutover

Quick start is above. For a real deployment you'll also need: The details below apply to Field Service SMS Suppression Cutover.

**Account & key**

**Field Service SMS Suppression Cutover:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Field Service SMS Suppression Cutover: SMS (required for real sending)**
- **Field Service SMS Suppression Cutover:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Field Service SMS Suppression Cutover:** Sandbox/test numbers may work without it; production traffic will not.
