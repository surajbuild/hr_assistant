"""
app/services/employee_service.py
--------------------------------
Service layer for employee profile business logic and database queries.

Contains reusable Python functions for:
- Retrieving the authenticated user's employee profile
- Retrieving all employees (for administrative/HR directory listing)
- Retrieving a specific employee by ID (with existence validation)
- Role-based data scope (which employee IDs a user may see)
- Employee CRUD (create with optional login account, update, soft delete)
- Department statistics (departments are derived from employees.department)

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be safely invoked by both API routers and AI/tool agents.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.models import Employee, EmployeeStatus, User, UserRole, UserStatus
from app.database.queries import get_all_employees as db_get_all_employees
from app.database.queries import get_employee_by_id as db_get_employee_by_id
from app.utils.security import hash_password


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class EmployeeServiceError(Exception):
    """Base exception for employee service operations."""
    pass


class EmployeeNotFoundError(EmployeeServiceError):
    """Raised when an operation targets an employee that does not exist."""
    pass


class EmployeeConflictError(EmployeeServiceError):
    """Raised when a unique value (employee code, login email) is already taken."""
    pass


class EmployeeValidationError(EmployeeServiceError):
    """Raised when employee data is logically invalid (e.g. self-manager)."""
    pass


# ---------------------------------------------------------------------------
# Queries / Retrieval
# ---------------------------------------------------------------------------

def get_my_profile(current_user: User) -> Employee:
    """
    Retrieve the employee profile associated with the authenticated user.

    Raises:
        EmployeeNotFoundError: If no linked employee record exists.

    Returns:
        Employee: The linked employee profile.
    """
    if not current_user.employee:
        raise EmployeeNotFoundError("Employee profile not found for the current user.")
    return current_user.employee


def get_all_employees(db: Session) -> List[Employee]:
    """
    Retrieve all employee records from the database.

    Returns:
        List[Employee]: All persisted employees.
    """
    return db_get_all_employees(db)


def get_employee_by_id(db: Session, employee_id: int) -> Employee:
    """
    Retrieve an employee record by their primary key ID.

    Validates that the employee exists.

    Raises:
        EmployeeNotFoundError: If the employee ID is not found.

    Returns:
        Employee: The employee record.
    """
    employee = db_get_employee_by_id(db, employee_id)
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")
    return employee


# ---------------------------------------------------------------------------
# Role-based Data Scope
# ---------------------------------------------------------------------------

def get_scope_employee_ids(db: Session, current_user: User) -> Optional[Set[int]]:
    """
    Return the set of employee IDs the user may access, or None for unrestricted.

    - admin / hr  -> None (company-wide)
    - manager     -> own employee id + direct reports (employees.manager_id)
    - employee    -> own employee id only
    """
    if current_user.role in (UserRole.ADMIN.value, UserRole.HR.value):
        return None
    own_id = current_user.employee_id
    if current_user.role == UserRole.MANAGER.value:
        report_ids = {
            row[0]
            for row in db.query(Employee.id).filter(Employee.manager_id == own_id).all()
        }
        return report_ids | {own_id}
    return {own_id}


def can_access_employee(db: Session, current_user: User, employee_id: int) -> bool:
    """True if the employee is inside the user's data scope."""
    scope = get_scope_employee_ids(db, current_user)
    return scope is None or employee_id in scope


# ---------------------------------------------------------------------------
# Listing with filters
# ---------------------------------------------------------------------------

def list_employees(
    db: Session,
    *,
    scope_ids: Optional[Set[int]] = None,
    search: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Employee]:
    """List employees inside `scope_ids` (None = all) with optional filters."""
    query = db.query(Employee)
    if scope_ids is not None:
        if not scope_ids:
            return []
        query = query.filter(Employee.id.in_(scope_ids))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Employee.name.ilike(like),
                Employee.employee_code.ilike(like),
                Employee.designation.ilike(like),
                Employee.department.ilike(like),
            )
        )
    if department:
        query = query.filter(Employee.department == department)
    if status:
        query = query.filter(Employee.status == status)
    return query.order_by(Employee.name.asc()).all()


def serialize_employee(employee: Employee, include_salary: bool = False) -> Dict[str, Any]:
    """
    Flatten an employee + linked login + manager name for API responses.

    `monthly_gross_salary` is confidential: callers pass include_salary=True only for
    HR/Admin viewers or the employee themself (D-021, AGENTS.md §3).
    """
    data = {
        "id": employee.id,
        "employee_code": employee.employee_code,
        "name": employee.name,
        "department": employee.department,
        "designation": employee.designation,
        "joining_date": employee.joining_date,
        "status": employee.status,
        "manager_id": employee.manager_id,
        "manager_name": employee.manager.name if employee.manager else None,
        "email": employee.user.email if employee.user else None,
        "role": employee.user.role if employee.user else None,
    }
    if include_salary:
        data["monthly_gross_salary"] = (
            float(employee.monthly_gross_salary) if employee.monthly_gross_salary is not None else None
        )
    return data


def can_view_salary(current_user: User, employee_id: int) -> bool:
    """HR/Admin see every salary; everyone else only their own."""
    return current_user.role in (UserRole.ADMIN.value, UserRole.HR.value) or current_user.employee_id == employee_id


# ---------------------------------------------------------------------------
# Creation / Modification
# ---------------------------------------------------------------------------

def _validate_manager(db: Session, manager_id: Optional[int], employee_id: Optional[int] = None) -> None:
    if manager_id is None:
        return
    if employee_id is not None and manager_id == employee_id:
        raise EmployeeValidationError("An employee cannot be their own manager.")
    if not db_get_employee_by_id(db, manager_id):
        raise EmployeeValidationError("Selected manager does not exist.")


def create_employee(
    db: Session,
    *,
    employee_code: str,
    name: str,
    department: str,
    designation: str,
    joining_date: date,
    status: str = EmployeeStatus.ACTIVE.value,
    manager_id: Optional[int] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: str = UserRole.EMPLOYEE.value,
    monthly_gross_salary: Optional[float] = None,
) -> Employee:
    """
    Create an employee and, when `email` is given, a linked login account.

    Raises:
        EmployeeConflictError: employee code or email already in use.
        EmployeeValidationError: invalid manager, or email without password.
    """
    code = employee_code.strip().upper()
    if db.query(Employee).filter(Employee.employee_code == code).first():
        raise EmployeeConflictError(f"Employee code '{code}' is already in use.")
    _validate_manager(db, manager_id)
    if email:
        if not password:
            raise EmployeeValidationError("A password is required to create a login account.")
        if db.query(User).filter(User.email == email.lower()).first():
            raise EmployeeConflictError(f"Email '{email}' is already registered.")

    employee = Employee(
        employee_code=code,
        name=name.strip(),
        department=department.strip(),
        designation=designation.strip(),
        joining_date=joining_date,
        status=status,
        manager_id=manager_id,
        monthly_gross_salary=monthly_gross_salary,
    )
    db.add(employee)
    db.flush()

    if email:
        db.add(
            User(
                employee_id=employee.id,
                email=email.lower(),
                password_hash=hash_password(password),
                role=role,
                status=UserStatus.ACTIVE.value,
            )
        )

    db.commit()
    db.refresh(employee)
    return employee


def update_employee(db: Session, employee_id: int, changes: Dict[str, Any]) -> Employee:
    """
    Apply a partial update to an employee profile.

    Raises:
        EmployeeNotFoundError, EmployeeConflictError, EmployeeValidationError
    """
    employee = get_employee_by_id(db, employee_id)
    allowed = {
        "employee_code", "name", "department", "designation", "joining_date", "status", "manager_id",
        "monthly_gross_salary",
    }

    if changes.get("employee_code"):
        code = changes["employee_code"].strip().upper()
        clash = (
            db.query(Employee)
            .filter(Employee.employee_code == code, Employee.id != employee_id)
            .first()
        )
        if clash:
            raise EmployeeConflictError(f"Employee code '{code}' is already in use.")
        changes["employee_code"] = code
    if "manager_id" in changes:
        _validate_manager(db, changes["manager_id"], employee_id)

    for field, value in changes.items():
        if field not in allowed:
            continue
        if isinstance(value, str):
            value = value.strip()
        setattr(employee, field, value)

    # Keep the linked login in sync with employment status
    if employee.user and "status" in changes:
        employee.user.status = (
            UserStatus.ACTIVE.value
            if employee.status == EmployeeStatus.ACTIVE.value
            else UserStatus.INACTIVE.value
        )

    db.commit()
    db.refresh(employee)
    return employee


def deactivate_employee(db: Session, employee_id: int) -> Employee:
    """
    Soft delete: mark the employee inactive and disable their login.
    History (attendance, leave, salary) is preserved.
    """
    employee = get_employee_by_id(db, employee_id)
    employee.status = EmployeeStatus.INACTIVE.value
    if employee.user:
        employee.user.status = UserStatus.INACTIVE.value
    db.commit()
    db.refresh(employee)
    return employee


# ---------------------------------------------------------------------------
# Departments (derived from employees.department)
# ---------------------------------------------------------------------------

def list_departments(db: Session, scope_ids: Optional[Set[int]] = None) -> List[Dict[str, Any]]:
    """Aggregate department statistics from employee rows."""
    employees = list_employees(db, scope_ids=scope_ids)
    manager_ids = {
        row[0] for row in db.query(Employee.manager_id).filter(Employee.manager_id.isnot(None)).distinct()
    }
    departments: Dict[str, Dict[str, Any]] = {}

    for emp in employees:
        dept = departments.setdefault(
            emp.department,
            {"name": emp.department, "employee_count": 0, "active_count": 0, "designations": set(), "managers": []},
        )
        dept["employee_count"] += 1
        if emp.status == EmployeeStatus.ACTIVE.value:
            dept["active_count"] += 1
        dept["designations"].add(emp.designation)
        if emp.id in manager_ids:
            dept["managers"].append(emp.name)

    result = []
    for dept in sorted(departments.values(), key=lambda d: d["name"]):
        dept["designations"] = sorted(dept["designations"])
        result.append(dept)
    return result
