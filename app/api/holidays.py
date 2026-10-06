"""
app/api/holidays.py
-------------------
Company holiday calendar (D-034).

Endpoints
---------
GET    /holidays          — National + declared holidays for a year (any authenticated user).
POST   /holidays          — Declare a company holiday (HR / Admin).
DELETE /holidays/{id}     — Remove a declared holiday (HR / Admin). National holidays cannot be removed.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import holiday_service
from app.services.holiday_service import HolidayConflictError, HolidayNotFoundError, InvalidHolidayError
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/holidays", tags=["Holidays"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HolidayItem(BaseModel):
    id: Optional[int] = None          # None for national holidays (defined in code)
    date: date
    name: str
    kind: str                         # "national" | "company"
    weekday: str


class HolidayListResponse(BaseModel):
    year: int
    items: List[HolidayItem]


class HolidayCreateRequest(BaseModel):
    holiday_date: date
    name: str = Field(..., min_length=1, max_length=255)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=HolidayListResponse,
    status_code=status.HTTP_200_OK,
    summary="Holiday Calendar",
    description="National and company holidays of one calendar year (default: current year).",
)
def list_holidays(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year = year or date.today().year
    return {"year": year, "items": holiday_service.list_holidays(db, year)}


@router.post(
    "",
    response_model=HolidayItem,
    status_code=status.HTTP_201_CREATED,
    summary="Declare Company Holiday",
    description="HR / Admin. Weekends and national holidays are rejected. Payroll and leave counting exclude the date.",
)
def create_holiday(
    body: HolidayCreateRequest,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    try:
        holiday = holiday_service.create_holiday(
            db, holiday_date=body.holiday_date, name=body.name, created_by=current_user.id
        )
    except InvalidHolidayError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except HolidayConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return {
        "id": holiday.id,
        "date": holiday.holiday_date,
        "name": holiday.name,
        "kind": "company",
        "weekday": holiday.holiday_date.strftime("%A"),
    }


@router.delete(
    "/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Company Holiday",
)
def delete_holiday(
    holiday_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    try:
        holiday_service.delete_holiday(db, holiday_id)
    except HolidayNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
