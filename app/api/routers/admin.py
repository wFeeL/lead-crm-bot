from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_api_admin_user
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AppError,
    InvalidStatusTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.security import require_admin_api_token
from app.db.dependencies import get_db
from app.db.models.user import User
from app.schemas.lead import DailyStatsRead, LeadCommentCreate, LeadRead, LeadStatusUpdate
from app.services.leads import LeadService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_token)],
)


def map_app_error(error: AppError) -> HTTPException:
    message = str(error) or error.__class__.__name__
    if isinstance(error, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
    if isinstance(error, PermissionDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
    if isinstance(error, InvalidStatusTransitionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    if isinstance(error, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


@router.get("/leads", response_model=list[LeadRead])
async def list_leads(
    status_filter: str | None = Query(default=None, alias="status"),
    user: str | None = Query(default=None, description="Telegram ID or username"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[LeadRead]:
    service = LeadService(session, settings)
    leads = await service.list_leads(
        status=status_filter,
        user_query=user,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [LeadRead.model_validate(lead) for lead in leads]


@router.get("/leads/export.csv")
async def export_leads(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    service = LeadService(session, settings)
    csv_payload = await service.export_csv()
    return Response(
        content=csv_payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


@router.get("/leads/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LeadRead:
    service = LeadService(session, settings)
    try:
        lead = await service.get_lead(lead_id)
    except AppError as exc:
        raise map_app_error(exc) from exc
    return LeadRead.model_validate(lead)


@router.patch("/leads/{lead_id}/status", response_model=LeadRead)
async def update_lead_status(
    lead_id: int,
    payload: LeadStatusUpdate,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    admin: User = Depends(get_api_admin_user),
) -> LeadRead:
    service = LeadService(session, settings)
    try:
        lead = await service.change_status(lead_id=lead_id, status=payload.status, actor=admin)
        await session.commit()
    except AppError as exc:
        await session.rollback()
        raise map_app_error(exc) from exc
    return LeadRead.model_validate(lead)


@router.post("/leads/{lead_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    lead_id: int,
    payload: LeadCommentCreate,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    admin: User = Depends(get_api_admin_user),
) -> dict[str, str]:
    service = LeadService(session, settings)
    try:
        await service.add_comment(
            lead_id=lead_id,
            admin=admin,
            text=payload.text,
            is_internal=payload.is_internal,
        )
        await session.commit()
    except AppError as exc:
        await session.rollback()
        raise map_app_error(exc) from exc
    return {"status": "ok"}


@router.get("/stats/daily", response_model=DailyStatsRead)
async def daily_stats(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DailyStatsRead:
    service = LeadService(session, settings)
    return await service.daily_stats()
