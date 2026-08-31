"""Safety-report routes (Phase 3B, DILCHAT-D3B-3/5).

Reports are durable and idempotent on (reporter, conversation,
client_report_id). There is deliberately NO moderation-transition surface and
NO reporter-facing evidence retrieval: responses carry only the
reporter-visible reference and status, and reports remain SUBMITTED until a
later explicit moderation phase. Future authorized moderation access will be a
separate privileged surface, never an extension of this reporter API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import ReportCreateRequest, ReportListResponse, ReportResponse

router = APIRouter(prefix="/reports", tags=["safety"])


def _report_response(report) -> ReportResponse:
    return ReportResponse(
        report_id=report.id,
        conversation_id=report.conversation_id,
        target_type=report.target_type,
        target_message_id=report.target_message_id,
        reason=report.reason,
        status=report.status,
        created_at=report.created_at,
    )


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> ReportResponse:
    report = await services.reports.create_report(
        reporter_user_id=principal.user_id,
        conversation_id=payload.conversation_id,
        target_type=payload.target_type,
        target_message_id=payload.target_message_id,
        reason=payload.reason,
        description=payload.description,
        client_report_id=payload.client_report_id,
        correlation_id=correlation_id,
    )
    return _report_response(report)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> ReportListResponse:
    reports = await services.reports.list_reports(principal.user_id)
    return ReportListResponse(reports=[_report_response(r) for r in reports])
