from enum import Enum
from datetime import date, datetime, time
from typing import Optional, List

from sqlalchemy import (
    String,
    Integer,
    Date,
    DateTime,
    Time,
    Text,
    Numeric,
    ForeignKey,
    func,
)
from sqlalchemy.orm import mapped_column, Mapped, DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    EMPLOYEE = "employee"
    HR = "hr"
    MANAGER = "manager"
    ADMIN = "admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_NOTICE = "on_notice"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    HALF_DAY = "half_day"
    LEAVE = "leave"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"


class LeaveType(str, Enum):
    CASUAL = "casual"
    SICK = "sick"
    EARNED = "earned"
    UNPAID = "unpaid"
    MATERNITY = "maternity"
    PATERNITY = "paternity"


class LeaveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    PROCESSING = "processing"
    FAILED = "failed"


class QueryIntent(str, Enum):
    EMPLOYEE_INFO = "employee_info"
    ATTENDANCE = "attendance"
    LEAVE = "leave"
    SALARY = "salary"
    OVERTIME = "overtime"
    POLICY = "policy"
    REPORT = "report"
    GENERAL = "general"
    UNKNOWN = "unknown"


class DataSource(str, Enum):
    ATTENDANCE_DATABASE = "attendance_database"
    SALARY_DATABASE = "salary_database"
    EMPLOYEE_DATABASE = "employee_database"
    LEAVE_DATABASE = "leave_database"
    DOCUMENT_RAG = "document_rag"
    GENERAL = "general"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Employee(Base):
    """
    Stores core employee profile information.
    Matches PRD Section 13 — employees table.
    """
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EmployeeStatus.ACTIVE.value
    )
    # Self-referential FK: points to the manager's employee row
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=True
    )

    # Salary structure used by the payroll engine (D-021). Confidential:
    # only HR/Admin and the employee themself may see it.
    monthly_gross_salary: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    # Relationships
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee", remote_side="Employee.id", back_populates="subordinates"
    )
    subordinates: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="manager"
    )
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="employee", uselist=False
    )
    attendance_records: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="employee"
    )
    leave_records: Mapped[List["Leave"]] = relationship(
        "Leave", back_populates="employee"
    )
    salary_records: Mapped[List["Salary"]] = relationship(
        "Salary", back_populates="employee"
    )


class User(Base):
    """
    Authentication and authorization record for a system user.
    Matches PRD Section 13 — users table.

    Supports two authentication methods:
      - Email + Password: password_hash is set; google_id is NULL.
      - Google OAuth:     google_id is set;    password_hash is NULL.
      - Both methods can coexist on the same account.

    password_hash is nullable so that Google-OAuth-only accounts do not
    need a fake placeholder password stored in the database.
    google_id is nullable (not all users sign in via Google) and unique
    (each Google account may only map to one system user).
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Nullable: Google-OAuth-only accounts will have NULL here
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Nullable: email/password accounts will have NULL here
    # Unique: one Google account → one system user
    google_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default=UserRole.EMPLOYEE.value
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=UserStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="user")
    chat_logs: Mapped[List["ChatLog"]] = relationship(
        "ChatLog", back_populates="user"
    )
    uploaded_documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="uploaded_by_user"
    )


class Attendance(Base):
    """
    Daily attendance record for an employee.
    Matches PRD Section 13 — attendance table.
    Supports: present/absent/late/overtime/working-hours queries (PRD Section 7, 10).
    """
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    in_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    out_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    # Total minutes actually worked that day
    working_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=AttendanceStatus.PRESENT.value
    )
    # Minutes after the standard start time the employee arrived
    late_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Overtime minutes beyond standard working hours
    overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee", back_populates="attendance_records"
    )


class Leave(Base):
    """
    Leave application record for an employee.
    Matches PRD Section 13 — leaves table.
    Supports: leave balance / history / who is on leave queries (PRD Section 9).
    """
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    leave_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LeaveType.CASUAL.value
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=LeaveStatus.PENDING.value
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee", back_populates="leave_records"
    )


class Salary(Base):
    """
    Monthly salary record for an employee.
    Matches PRD Section 13 — salary table.
    Supports: salary / deductions / PF / overtime-amount queries (PRD Section 8).
    """
    __tablename__ = "salary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)   # 1-12
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pf: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    deductions: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    overtime_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    net_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee", back_populates="salary_records"
    )


class Document(Base):
    """
    HR policy / company document uploaded for RAG indexing.
    Matches PRD Section 23 — Document Management.
    Tracks: name, upload_date, uploaded_by, version, status.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Original filename as uploaded
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Relative path where the file is stored on disk
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, docx, txt
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentStatus.PROCESSING.value
    )
    uploaded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    upload_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # Number of chunks created during RAG processing
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Parsing / indexing failure reason (status == failed)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    uploaded_by_user: Mapped["User"] = relationship(
        "User", back_populates="uploaded_documents"
    )
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """
    One retrievable text chunk of an indexed document (PRD Section 12 — RAG).

    term_vector holds a JSON object {term: count} — the sparse lexical
    "embedding" used for BM25 similarity search (see D-004).
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1-based page number for PDFs; NULL for formats without pages
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    term_vector: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class ChatLog(Base):
    """
    Immutable log of every AI chat interaction.
    Matches PRD Section 28 — Logging requirements.
    Fields: user_id, question, detected_intent, data_source,
            response, timestamp, response_time, error.
    """
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    detected_intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # How long the AI took to respond, in milliseconds
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chat_logs")