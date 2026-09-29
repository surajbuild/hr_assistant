"""
app/database/queries.py
-----------------------
Low-level CRUD helpers.  Each function receives a SQLAlchemy Session and
returns ORM objects (or None).  No business logic lives here.
"""

from datetime import date
from sqlalchemy.orm import Session

from app.database.models import Employee, User, EmployeeStatus, UserRole, UserStatus


# ---------------------------------------------------------------------------
# Employee queries
# ---------------------------------------------------------------------------

def create_employee(
    db: Session,
    *,
    employee_code: str,
    name: str,
    department: str,
    designation: str,
    joining_date: date,
    status: str = EmployeeStatus.ACTIVE.value,
    manager_id: int | None = None,
) -> Employee:
    """Insert a new employee row and return the persisted object."""
    employee = Employee(
        employee_code=employee_code,
        name=name,
        department=department,
        designation=designation,
        joining_date=joining_date,
        status=status,
        manager_id=manager_id,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def get_employee_by_id(db: Session, employee_id: int) -> Employee | None:
    """Return an employee by primary key, or None if not found."""
    return db.get(Employee, employee_id)


def get_employee_by_code(db: Session, employee_code: str) -> Employee | None:
    """Return an employee by their unique employee code, or None."""
    return db.query(Employee).filter(Employee.employee_code == employee_code).first()


def get_all_employees(db: Session) -> list[Employee]:
    """Return all employee records from the database."""
    return db.query(Employee).all()


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------

def create_user(
    db: Session,
    *,
    employee_id: int,
    email: str,
    password_hash: str | None = None,
    google_id: str | None = None,
    role: str = UserRole.EMPLOYEE.value,
    status: str = UserStatus.ACTIVE.value,
) -> User:
    """Insert a new user row and return the persisted object."""
    user = User(
        employee_id=employee_id,
        email=email,
        password_hash=password_hash,
        google_id=google_id,
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return a user by their unique email, or None if not found."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str) -> User | None:
    """Return a user by their unique google_id, or None if not found."""
    return db.query(User).filter(User.google_id == google_id).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Return a user by primary key, or None if not found."""
    return db.get(User, user_id)
