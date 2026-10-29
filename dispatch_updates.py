from __future__ import annotations

from fastapi import FastAPI, HTTPException

from field_follow_up import FollowUpDecision, InfraiSMSGateway, WorkOrderFollowUpRequest, process_follow_up
from infrai_client import InfraiError


app = FastAPI(title="Field Service SMS Follow-Up Service")


@app.post("/follow-up", response_model=FollowUpDecision)
def create_follow_up(request: WorkOrderFollowUpRequest) -> FollowUpDecision:
    try:
        return process_follow_up(request, sms_gateway=InfraiSMSGateway())
    except InfraiError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "error": exc.detail}) from exc
