"""
app/api/departments.py
----------------------
Department overview routes.

Departments are derived from `employees.department` (there is no departments
table — see PROJECT_DECISIONS.md D-005).

Endpoints
---------
GET /departments — Department statistics. HR / Admin: all; Manager: own team only.
"""

from typing import List

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import employee_service
from app.utils.dependencies import require_role

router = APIRouter(prefix="/departments", tags=["Departments"])


class DepartmentResponse(BaseModel):
    name: str
    employee_count: int
    active_count: int
    designations: List[str]
    managers: List[str]


@router.get(
    "",
    response_model=List[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Departments",
)
def list_departments(
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    return employee_service.list_departments(db, scope_ids=scope)
