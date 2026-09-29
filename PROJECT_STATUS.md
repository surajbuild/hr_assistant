# AI HR Assistant - Project Status

## 1. Current Overall Status
The AI HR Assistant project is currently in the **Backend Foundation & Core HR Data Layer** phase.

Based on the 8-stage timeline established in the Product Requirements Document (PRD):
- **Completed**: Foundation setup, MySQL schema, Alembic migrations, Authentication (Bcrypt + JWT), Role-Based Access Control (RBAC), and individual REST API modules for Employees, Leaves, Attendance, and Salary.
- **Partially Completed**: Business logic and database queries (currently embedded directly inside API route handlers rather than segregated in the service layer), database preparation for Google OAuth, and core API test coverage.
- **Not Started**: The entire AI and RAG stack (AI Router, LLM API client, Prompt Management, Tool Calling, Document Ingestion, Chunking, Embeddings, Vector Database, RAG Retrieval, Guardrails/Hallucination prevention), Audit Logging, Excel Reports generation, and the Frontend UI (Dashboard and Chat Interface).

| Module / Milestone | Status | Description |
| :--- | :--- | :--- |
| **Project & Environment Setup** | **Completed** | FastAPI app, PyMySQL, SQLAlchemy, Alembic, Virtual environment configured. |
| **Database & Schema Modeling** | **Completed** | All 7 domain tables + Alembic migration tracking live in MySQL. |
| **Authentication & RBAC** | **Completed** | Secure password hashing, JWT Bearer issuance, active user check, role enforcement. |
| **Employee Module APIs** | **Partially Completed** | `GET /employees/me` implemented & tested. General list and ID lookup pending. |
| **Leave Management APIs** | **Partially Completed** | `POST /leaves`, `GET /leaves/me`, `PATCH /leaves/{id}/status` implemented. Employee ID lookup pending. |
| **Attendance Management APIs** | **Completed** | `GET /attendance/me`, `POST /attendance`, `GET /attendance/summary`, `GET /attendance/{id}` implemented. |
| **Salary Management APIs** | **Partially Completed** | `GET /salary/me`, `GET /salary/{id}` implemented. `GET /salary/summary` pending. |
| **Business Services / Calculation Engine** | **Partially Completed** | Attendance summary calculation logic exists in route handler; `app/services/` files are empty stubs. |
| **AI Layer & LLM Integration** | **Not Started** | Chat endpoint, intent classification, prompts, guardrails, LLM provider integration absent. |
| **Document Ingestion & RAG** | **Not Started** | PDF/DOCX loaders, text cleaning, chunking, embeddings, and vector store absent. |
| **Chat Logging & Auditing** | **Not Started** | `chat_logs` table exists; logging interceptor/service absent (`app/utils/logging.py` empty). |
| **Reports & Excel Export** | **Not Started** | Attendance, Leave, and Overtime reporting with Excel export absent. |
| **Web Frontend & Dashboard** | **Not Started** | `frontend/` directory is completely empty; no UI or dashboard charts implemented. |

---

## 2. Architecture Currently Implemented

### Current Implemented Flow

```
                      ┌──────────────────────────────────────────────┐
                      │        Client (Browser / API Client)         │
                      └──────────────────────┬───────────────────────┘
                                             │ HTTP Request
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │              FastAPI Application             │
                      │                (app/main.py)                 │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │          Authentication & RBAC Layer         │
                      │     (app/utils/security.py & dependencies.py)│
                      │  • Bearer Token Extraction (HTTPBearer)      │
                      │  • JWT Validation & Decode (HS256)           │
                      │  • User Status Check (Active / Inactive)     │
                      │  • Role Enforcement (require_role)           │
                      └──────────────────────┬───────────────────────┘
                                             │ Authenticated & Authorized
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │             Business API Routers             │
                      │                 (app/api/)                   │
                      │  • /auth         • /employees                │
                      │  • /leaves       • /attendance               │
                      │  • /salary                                   │
                      └──────────────────────┬───────────────────────┘
                                             │ Direct ORM Session Queries
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │         SQLAlchemy ORM & Connection          │
                      │     (app/database/models.py & connection.py) │
                      └──────────────────────┬───────────────────────┘
                                             │ PyMySQL Driver
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │             MySQL Database (Local)           │
                      │  Tables: users, employees, attendance,       │
                      │          leaves, salary, documents, chat_logs│
                      └──────────────────────────────────────────────┘
```

### Planned Components NOT Implemented Yet

```
                      [Web Frontend / Dashboard] (frontend/ - Empty)
                                   │
                                   ▼
                      [AI Chat Endpoint] (POST /chat - Empty)
                                   │
                                   ▼
                      [AI Router & Intent Detector] (app/ai/router.py - Empty)
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
    [Controlled DB Tools / Services]     [RAG Pipeline & Vector DB]
   (app/services/ - Empty Stubs)         (app/rag/ - Empty Stubs)
   • Attendance Calculation Engine       • Document Loader (PDF/DOCX)
   • Salary & Overtime Calculation       • Text Chunking & Embeddings
   • Leave Balance Calculator            • Vector Database (FAISS/Chroma)
                 │                                   │
                 └─────────────────┬─────────────────┘
                                   ▼
                      [LLM Client & Guardrails] (app/ai/llm.py, guardrails.py - Empty)
                                   │
                                   ▼
                      [Audit Logging] (app/utils/logging.py - Empty)
```

---

## 3. Completed Features

### 1. FastAPI Setup
- **What exists**: FastAPI application instantiated with OpenAPI docs, metadata, route grouping via APIRouter, and health-check root endpoint.
- **Important files**: `app/main.py`
- **Relevant endpoint(s)**: `GET /`
- **Tests available**: Verified in all integration test suites via FastAPI `TestClient`.
- **Test result**: PASS (returns HTTP 200 `{"message": "AI HR Assistant is Running"}`).

### 2. MySQL, SQLAlchemy & Alembic
- **What exists**: MySQL connectivity using PyMySQL and SQLAlchemy 2.0 ORM (`engine`, `SessionLocal`, `Base`, `get_db` generator). Declarative models for 7 domain tables. Alembic database migration environment with 2 applied migrations matching current head.
- **Important files**: `app/database/connection.py`, `app/database/models.py`, `app/database/queries.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/1b723488096a_create_initial_tables.py`, `alembic/versions/c0b131e5fbaa_add_google_id_and_nullable_password_.py`.
- **Relevant endpoint(s)**: N/A (Core Data Infrastructure).
- **Tests available**: `tests/test_database.py`.
- **Test result**: PASS (5 assertions passed).

### 3. Password Hashing & Verification
- **What exists**: Secure password management using `bcrypt` with work factor 12. Generates salted hashes and performs constant-time password verification.
- **Important files**: `app/utils/security.py` (`hash_password`, `verify_password`).
- **Relevant endpoint(s)**: Consumed during `POST /auth/login`.
- **Tests available**: `tests/test_security.py`.
- **Test result**: PASS (7 assertions passed).

### 4. JWT Token Generation & Decoding
- **What exists**: HS256-signed JWT generation containing `sub` (user_id), `role`, `iat`, and `exp`. Decoding function validates cryptographic signatures, expiry, and payload integrity, returning a structured `TokenData` object.
- **Important files**: `app/utils/security.py` (`create_access_token`, `decode_access_token`).
- **Relevant endpoint(s)**: Consumed across all authenticated routes.
- **Tests available**: `tests/test_jwt.py`.
- **Test result**: PASS (10 assertions passed).

### 5. Login API
- **What exists**: `POST /auth/login` endpoint accepting email and password, querying `users` by email, verifying bcrypt hash, ensuring `status == "active"`, and issuing a Bearer JWT. Uses generic failure messaging to prevent account enumeration.
- **Important files**: `app/api/auth.py`.
- **Relevant endpoint(s)**: `POST /auth/login`.
- **Tests available**: `tests/test_auth_login.py`.
- **Test result**: PASS (10 assertions passed).

### 6. Authentication Dependency (`get_current_user`)
- **What exists**: FastAPI dependency extracting Bearer tokens from the `Authorization` header, validating JWTs, loading user from DB, and asserting active status.
- **Important files**: `app/utils/dependencies.py` (`get_current_user`).
- **Relevant endpoint(s)**: Reusable dependency across all secure endpoints.
- **Tests available**: `tests/test_dependencies.py`.
- **Test result**: PASS (7 assertions passed).

### 7. Role-Based Access Control (`require_role`)
- **What exists**: Parameterized dependency factory enforcing role permissions (`employee`, `hr`, `manager`, `admin`). Returns HTTP 403 Forbidden on role mismatch.
- **Important files**: `app/utils/dependencies.py` (`require_role`).
- **Relevant endpoint(s)**: Consumed by administrative and managerial endpoints.
- **Tests available**: `tests/test_roles.py`.
- **Test result**: PASS (5 assertions passed).

### 8. Employees API
- **What exists**: Endpoint retrieving the authenticated employee's profile via SQLAlchemy relationship traversal (`current_user.employee`).
- **Important files**: `app/api/employees.py`.
- **Relevant endpoint(s)**: `GET /employees/me`.
- **Tests available**: `tests/test_employees.py`.
- **Test result**: PASS (4 assertions passed).

### 9. Leave Management APIs
- **What exists**: Application submission (`POST /leaves`) with date validation (`start_date <= end_date`), personal leave retrieval (`GET /leaves/me`), and status approval/rejection (`PATCH /leaves/{leave_id}/status`) restricted to HR and Managers.
- **Important files**: `app/api/leaves.py`.
- **Relevant endpoint(s)**: `POST /leaves`, `GET /leaves/me`, `PATCH /leaves/{leave_id}/status`.
- **Tests available**: `tests/test_leaves.py`, `tests/test_leaves_get.py`, `tests/test_leaves_patch.py`.
- **Test result**: PASS (19 total assertions passed across 3 test files).

### 10. Attendance Management APIs
- **What exists**: Employee attendance history (`GET /attendance/me`), HR/Admin attendance record creation (`POST /attendance`) with duplicate prevention (HTTP 409), HR/Admin employee attendance view (`GET /attendance/{employee_id}`), and attendance metrics summary (`GET /attendance/summary`) calculating present, absent, half-day, leave, holiday, weekend, late days, overtime days, total working minutes, and total overtime minutes with optional date filtering.
- **Important files**: `app/api/attendance.py`.
- **Relevant endpoint(s)**: `GET /attendance/me`, `POST /attendance`, `GET /attendance/summary`, `GET /attendance/{employee_id}`.
- **Tests available**: `tests/test_attendance_get.py`, `tests/test_attendance_post.py`, `tests/test_attendance_summary.py`, `tests/test_attendance_get_by_id.py`.
- **Test result**: PASS (40 total assertions passed across 4 test files).

### 11. Salary APIs
- **What exists**: Personal salary history (`GET /salary/me`) strictly isolated to the authenticated user's employee ID, and administrative salary lookup (`GET /salary/{employee_id}`) restricted to HR and Admin roles.
- **Important files**: `app/api/salary.py`.
- **Relevant endpoint(s)**: `GET /salary/me`, `GET /salary/{employee_id}`.
- **Tests available**: `tests/test_salary_get.py`, `tests/test_salary_get_by_id.py`.
- **Test result**: PASS (16 total assertions passed across 2 test files).

---

## 4. Authentication & Security Status

| Security Feature | Status | Evidence | Notes |
| :--- | :--- | :--- | :--- |
| **Password Hashing** | **Implemented & Tested** | `app/utils/security.py:28-45` | Uses `bcrypt` with work factor 12. |
| **Password Verification** | **Implemented & Tested** | `app/utils/security.py:47-72` | Uses constant-time `bcrypt.checkpw`. |
| **JWT Signing** | **Implemented & Tested** | `app/utils/security.py:123-157` | Signs `sub`, `role`, `iat`, `exp` with HS256. |
| **JWT Expiration** | **Implemented & Tested** | `app/utils/security.py:159-203` | Enforces expiration; raises `InvalidTokenError`. |
| **Bearer Token Validation** | **Implemented & Tested** | `app/utils/dependencies.py:31-88` | Parses HTTP Bearer authorization header. |
| **Active-User Check** | **Implemented & Tested** | `app/api/auth.py:84`, `app/utils/dependencies.py:81` | Returns HTTP 403 if `user.status != 'active'`. |
| **Role-Based Authorization (RBAC)** | **Implemented & Tested** | `app/utils/dependencies.py:90-114` | `require_role()` dependency rejects unauthorized roles with 403. |
| **Employee Data Isolation** | **Implemented & Tested** | `GET /employees/me`, `GET /leaves/me`, `GET /attendance/me`, `GET /attendance/summary` | Queries bind strictly to `current_user.employee.id`; immune to client parameter injection. |
| **Salary Data Isolation** | **Implemented & Tested** | `GET /salary/me`, `GET /salary/{employee_id}` | Employees cannot query other salaries; path-based employee query restricted to HR/Admin. |
| **Generic Login Error Messages** | **Implemented & Tested** | `app/api/auth.py:42-49` | Returns identical 401 error message for bad email or bad password to prevent user enumeration. |
| **Secret Management** | **Implemented & Tested** | `app/utils/security.py:88-96` | Secrets loaded from environment; fails fast if `JWT_SECRET_KEY` is missing. |
| **Input Validation** | **Implemented & Tested** | Pydantic models across `app/api/` | Validates date chronology, enum constraints, string limits, and email formats (422 on failure). |
| **API Authorization Enforcement** | **Implemented & Tested** | All private routes inject `get_current_user` or `require_role` | Returns HTTP 401 if token is missing, expired, or invalid. |
| **Google OAuth Authentication** | **Partially Completed** | `models.py:User.google_id`, migration `c0b131e5fbaa` | DB schema supports Google OAuth, but route and OAuth handshake are not yet implemented. |
| **Prompt Injection Protection** | **Not Started** | `app/ai/guardrails.py` is empty (0 bytes) | No guardrails or prompt filters are implemented yet. |

---

## 5. Current API Inventory

| Method | Endpoint | Auth | Role | Purpose | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GET** | `/` | None | Public | Health check / system status | Implemented & Working |
| **POST** | `/auth/login` | None | Public | User authentication & JWT issuance | Implemented & Tested |
| **GET** | `/employees/me` | Bearer JWT | Authenticated Employee | Retrieve current user's employee profile | Implemented & Tested |
| **POST** | `/leaves` | Bearer JWT | Authenticated Employee | Submit a new leave request (pending status) | Implemented & Tested |
| **GET** | `/leaves/me` | Bearer JWT | Authenticated Employee | Retrieve leave history for current user | Implemented & Tested |
| **PATCH** | `/leaves/{leave_id}/status` | Bearer JWT | HR, Manager | Approve or reject a pending leave application | Implemented & Tested |
| **GET** | `/attendance/me` | Bearer JWT | Authenticated Employee | Retrieve attendance logs for current user | Implemented & Tested |
| **POST** | `/attendance` | Bearer JWT | HR, Admin | Create attendance record (prevents duplicates) | Implemented & Tested |
| **GET** | `/attendance/summary` | Bearer JWT | Authenticated Employee | Retrieve aggregated attendance metrics | Implemented & Tested |
| **GET** | `/attendance/{employee_id}` | Bearer JWT | HR, Admin | Retrieve attendance records for specific employee | Implemented & Tested |
| **GET** | `/salary/me` | Bearer JWT | Authenticated Employee | Retrieve salary records for current user | Implemented & Tested |
| **GET** | `/salary/{employee_id}` | Bearer JWT | HR, Admin | Retrieve salary records for specific employee | Implemented & Tested |

---

## 6. Database Status

### Tables Implemented in MySQL
1. **`employees`**: Stores core profiles.
   - *Columns*: `id` (PK), `employee_code` (UQ), `name`, `department`, `designation`, `joining_date`, `status`, `manager_id` (FK -> `employees.id`).
2. **`users`**: System credentials and roles.
   - *Columns*: `id` (PK), `employee_id` (FK -> `employees.id`, UQ), `email` (UQ), `password_hash` (nullable), `google_id` (UQ, nullable), `role`, `status`, `created_at`, `updated_at`.
3. **`attendance`**: Daily attendance entries.
   - *Columns*: `id` (PK), `employee_id` (FK -> `employees.id`), `attendance_date`, `in_time`, `out_time`, `working_minutes`, `status`, `late_minutes`, `overtime_minutes`.
4. **`leaves`**: Employee leave requests and lifecycle.
   - *Columns*: `id` (PK), `employee_id` (FK -> `employees.id`), `leave_type`, `from_date`, `to_date`, `status`, `reason`, `applied_at`, `approved_by` (FK -> `users.id`).
5. **`salary`**: Monthly compensation details.
   - *Columns*: `id` (PK), `employee_id` (FK -> `employees.id`), `month`, `year`, `gross_salary`, `pf`, `deductions`, `overtime_amount`, `net_salary`, `paid_at`.
6. **`documents`**: Metadata for uploaded HR documents intended for RAG indexing.
   - *Columns*: `id` (PK), `name`, `file_name`, `file_path`, `file_type`, `version`, `status`, `uploaded_by` (FK -> `users.id`), `upload_date`, `chunk_count`.
7. **`chat_logs`**: AI interaction history.
   - *Columns*: `id` (PK), `user_id` (FK -> `users.id`), `question`, `detected_intent`, `data_source`, `response`, `timestamp`, `response_time_ms`, `error`.
8. **`alembic_version`**: Migration revision state tracking.

### Key ORM Relationships
- `Employee.user` ↔ `User.employee` (One-to-One)
- `Employee.attendance_records` ↔ `Attendance.employee` (One-to-Many)
- `Employee.leave_records` ↔ `Leave.employee` (One-to-Many)
- `Employee.salary_records` ↔ `Salary.employee` (One-to-Many)
- `Employee.subordinates` ↔ `Employee.manager` (Self-referential One-to-Many)
- `User.chat_logs` ↔ `ChatLog.user` (One-to-Many)
- `User.uploaded_documents` ↔ `Document.uploaded_by_user` (One-to-Many)

### Migrations
- `1b723488096a`: Initial schema creation for all 7 domain tables.
- `c0b131e5fbaa`: Alteration adding `google_id` and nullable `password_hash` to `users`.
- **Current Alembic Head**: `c0b131e5fbaa` (Fully applied and in sync with the database).

### Implemented vs Pending Database Functionality
- **Implemented**: ORM models, relationships, field constraints, schema migrations, and connection pooling. Low-level CRUD for `Employee` and `User` in `app/database/queries.py`.
- **Pending**:
  - Reusable helper queries for `Attendance`, `Leave`, `Salary`, `Document`, and `ChatLog` in `app/database/queries.py` (queries are currently written ad-hoc in router handlers).
  - Database seeding scripts for demo and development data (e.g., sample employees "Aman", "Rahul", and standard monthly attendance/salary history).

---

## 7. Test Coverage

| Test File | Feature Tested | Assertions Passed | Result |
| :--- | :--- | :--- | :--- |
| `tests/test_attendance_get.py` | `GET /attendance/me` (personal records, isolation, empty state, 401 unauth) | 6 | PASS |
| `tests/test_attendance_get_by_id.py` | `GET /attendance/{id}` (HR/Admin access, employee 403, 401 unauth, 404 missing) | 6 | PASS |
| `tests/test_attendance_post.py` | `POST /attendance` (HR/Admin creation, employee 403, 404 missing emp, 409 duplicate) | 8 | PASS |
| `tests/test_attendance_summary.py` | `GET /attendance/summary` (status counts, late/OT days, minutes sums, date filter, 422, 401) | 20 | PASS |
| `tests/test_auth_login.py` | `POST /auth/login` (valid token, claims, invalid password/email 401, inactive 403, 422) | 10 | PASS |
| `tests/test_database.py` | Database layer CRUD (`create_employee`, `create_user`, query by id/email/code) | 5 | PASS |
| `tests/test_dependencies.py` | `get_current_user` (valid token, missing header, invalid/expired token, inactive user) | 7 | PASS |
| `tests/test_employees.py` | `GET /employees/me` (authenticated profile retrieval, 401 missing token) | 4 | PASS |
| `tests/test_jwt.py` | JWT utilities (signing, decoding, claims validation, tampering, expiration) | 10 | PASS |
| `tests/test_leaves.py` | `POST /leaves` (request creation, pending default, 401 unauth, date order 422) | 5 | PASS |
| `tests/test_leaves_get.py` | `GET /leaves/me` (retrieval, employee isolation, empty state 200, 401 unauth) | 6 | PASS |
| `tests/test_leaves_patch.py` | `PATCH /leaves/{id}/status` (HR approval, Manager rejection, 403 employee, 404, 400 state) | 8 | PASS |
| `tests/test_roles.py` | `require_role()` dependency (allowed roles 200, forbidden roles 403, unauthenticated 401) | 5 | PASS |
| `tests/test_salary_get.py` | `GET /salary/me` (personal history, cross-employee isolation, empty state 200, 401) | 7 | PASS |
| `tests/test_salary_get_by_id.py` | `GET /salary/{id}` (HR/Admin access, employee 403, unauth 401, 404 missing, empty list 200) | 9 | PASS |
| `tests/test_security.py` | Password hashing (bcrypt work factor, salt uniqueness, matching & mismatch verification) | 7 | PASS |

### Test Summary
- **Total Test Files**: 16
- **Known Passing Assertions**: 123
- **Known Failures**: 0
- **Areas with No Tests Yet**:
  - AI chat endpoints (`POST /chat`)
  - AI router / intent detection
  - LLM integration and prompt execution
  - Document parsing, text chunking, and embedding generation
  - Vector similarity search / RAG retriever
  - Prompt injection guardrails & hallucination prevention
  - Audit logging to `chat_logs`
  - Excel report exports
  - Google OAuth token exchange

---

## 8. PRD Comparison

| PRD Requirement | Status | Existing Implementation | Remaining Work |
| :--- | :--- | :--- | :--- |
| **Natural-Language HR Q&A** | **Not Started** | None (`app/api/chat.py` is 0 bytes) | Implement `POST /chat`, request/response orchestration, LLM conversation state. |
| **Intent Detection** | **Not Started** | `QueryIntent` enum in `models.py`; `app/ai/router.py` is 0 bytes | Build intent classification engine (EMPLOYEE_INFO, ATTENDANCE, LEAVE, SALARY, OVERTIME, POLICY, REPORT, GENERAL). |
| **MySQL Retrieval via AI** | **Not Started** | Low-level database models and queries exist | Implement controlled Python tool-calling layer for safe SQL parameterization without raw SQL generation. |
| **RAG System** | **Not Started** | `documents` table in DB; `app/rag/` files are 0 bytes | End-to-end RAG pipeline: document loader, text chunking, embedding generation, vector store index, retriever. |
| **Document Upload** | **Not Started** | `documents` table exists in DB | Implement `POST /documents/upload` and `GET /documents` endpoints with file validation and storage. |
| **PDF/DOCX/TXT Parsing** | **Not Started** | `python-docx` installed; `app/rag/document_loader.py` is 0 bytes | Implement parsers for PDF (pypdf/pymupdf), DOCX (`python-docx`), and plain text. |
| **Cleaning & Chunking** | **Not Started** | `app/rag/chunker.py` is 0 bytes | Implement text normalization and recursive/character chunking with overlap. |
| **Embeddings Generation** | **Not Started** | `app/rag/embeddings.py` is 0 bytes | Connect to embedding model API (OpenAI / Google Gemini Embeddings). |
| **Vector Database** | **Not Started** | None | Integrate and configure vector store (FAISS or Chroma) with persistent disk storage. |
| **RAG Retrieval** | **Not Started** | `app/rag/retrievers.py` is 0 bytes | Implement similarity search, top-k filtering, and citation linking. |
| **Calculation Engine** | **Partially Completed** | Attendance summary calculation in route handler | Abstract calculations into dedicated `app/services/` for attendance, overtime, salary, and leave balances. |
| **Permissions & RBAC** | **Completed (Core)** | Full JWT + `get_current_user` + `require_role` implemented | Implement manager team-hierarchy filtering and AI prompt-level permission enforcement. |
| **Hallucination Prevention / Guardrails** | **Not Started** | `app/ai/guardrails.py` is 0 bytes | Build system prompts enforcing "I could not find..." fallback, factual grounding, and prompt injection filters. |
| **Query / Response Logging** | **Partially Completed** | `chat_logs` table schema exists in DB | Implement logging service in `app/utils/logging.py` to record user query, intent, data source, answer, latency, error. |
| **Google OAuth** | **Partially Completed** | `google_id` and nullable `password_hash` in `users` | Implement Google OAuth 2.0 exchange endpoint (`/auth/google/callback`) and token creation. |
| **Frontend Web Interface** | **Not Started** | `frontend/` directory is empty | Build user web app (HTML/CSS/JS/Bootstrap): Login, Chat UI, and Analytics Dashboard. |
| **Admin Document Management** | **Partially Completed** | `documents` table exists in DB | Build document management endpoints and admin upload/indexing UI. |
| **AI Tools / Services** | **Not Started** | `app/services/` files are 0 bytes | Define callable Python tools for AI to query attendance, leave, salary, and policy documents. |

---

## 9. Not Started

The following major features are completely absent from the codebase:
1. **AI Chat API (`POST /chat`)**: The conversational entry point for users to ask questions.
2. **AI Intent Classification (`app/ai/router.py`)**: Determining whether a user query pertains to attendance, salary, leave, policies, or general conversation.
3. **LLM Client & Orchestrator (`app/ai/llm.py`)**: Integration with an LLM provider (e.g., Google Gemini or OpenAI) to generate final natural language answers.
4. **Prompt Management (`app/ai/prompts.py`)**: System instructions, few-shot examples, and dynamic context assembly.
5. **AI Guardrails & Prompt Injection Protection (`app/ai/guardrails.py`)**: Defense against system prompt overrides and unauthorized data requests.
6. **RAG Pipeline (`app/rag/`)**: Document loading (PDF/DOCX/TXT), text cleaning, chunking, embeddings, vector database integration (FAISS/Chroma), and similarity retrieval.
7. **Document Upload APIs (`POST /documents/upload`, `GET /documents`)**: Administrative endpoints to upload and inspect indexed HR documents.
8. **Excel Reports Generation**: Attendance, overtime, and leave report generation exported to `.xlsx` using Pandas / OpenPyXL.
9. **Frontend Web Application (`frontend/`)**: HTML/CSS/JavaScript web dashboard, chat UI, and analytics charts.
10. **Manager Team-Hierarchy Authorization**: Logic ensuring managers can only inspect records for employees in their reporting chain.

---

## 10. Partially Completed

The following modules have foundational groundwork in place but are not fully implemented:
1. **Business Service Layer**:
   - The route handlers in `app/api/attendance.py` and `app/api/salary.py` currently perform database queries and aggregations directly.
   - The corresponding service files (`app/services/attendance_service.py`, `salary_service.py`, `leave_service.py`) are empty (0 bytes). These calculations must be factored out so the AI tools can invoke them directly.
2. **Database Query Abstraction (`app/database/queries.py`)**:
   - Only basic queries for `Employee` and `User` are defined.
   - Attendance, leave, salary, document, and chat log database operations have no centralized helper functions in `queries.py`.
3. **Google OAuth 2.0**:
   - The database schema supports OAuth (`google_id` column and nullable `password_hash` in `users`).
   - The actual OAuth login route, redirect handling, and token exchange are not implemented.
4. **Audit Logging**:
   - The `chat_logs` table exists in MySQL with fields for query, intent, data source, response, latency, and error.
   - `app/utils/logging.py` is empty (0 bytes), and no requests or queries are currently logged.
5. **Missing PRD Endpoints**:
   - `GET /employees` (List all employees) and `GET /employees/{id}` (Get specific employee).
   - `GET /leaves/{employee_id}` (Get specific employee's leaves).
   - `GET /salary/summary` (Aggregated payroll statistics).

---

## 11. Recommended Build Order

To ensure components are built upon stable dependencies without rework, the recommended development progression is:

### Stage 1: Service Layer Refactoring & Query Helpers
- **What**: Move business calculations and SQL queries out of `app/api/` route handlers into `app/services/` (`attendance_service.py`, `salary_service.py`, `leave_service.py`) and `app/database/queries.py`.
- **Why**: The AI agent will need to call these Python functions directly as tools. Decoupling business logic from FastAPI HTTP request objects is necessary before tool-calling can be implemented.

### Stage 2: Missing Core REST Endpoints & Database Seeding
- **What**: Implement `GET /employees`, `GET /employees/{id}`, `GET /leaves/{employee_id}`, and `GET /salary/summary`. Create a comprehensive database seed script with sample employees ("Aman", "Rahul"), departments, attendance records, leaves, and salary slips.
- **Why**: Fulfills the baseline PRD REST specifications and provides real data for the AI agent to retrieve and calculate against during development and demo verification.

### Stage 3: AI Foundation (LLM Integration, Router & Prompts)
- **What**: Rename `app/ai/lim.py` to `llm.py` and configure the LLM provider client (e.g., Google Gemini / OpenAI). Implement intent detection in `app/ai/router.py` and base system prompts in `app/ai/prompts.py`.
- **Why**: Establishes the core AI brain and query routing before attaching external tools and knowledge bases.

### Stage 4: Controlled Database Tool Calling
- **What**: Implement tool definitions mapping intents (ATTENDANCE, SALARY, LEAVE, EMPLOYEE_INFO) to the service functions created in Stage 1. Connect the AI router to execute these tools based on user permissions.
- **Why**: Delivers the primary PRD objective of enabling natural-language queries against MySQL data while enforcing data privacy and preventing SQL injection.

### Stage 5: Document Management & RAG Pipeline
- **What**: Implement document parsing (PDF, DOCX, TXT), text chunking (`chunker.py`), embedding generation (`embeddings.py`), vector database storage (FAISS or Chroma), and retrieval (`retrievers.py`). Add `POST /documents/upload` and `GET /documents`.
- **Why**: Enables answering HR policy questions from company documents (PRD Feature 7 & 12).

### Stage 6: Guardrails, Hallucination Prevention & Audit Logging
- **What**: Implement prompt injection protection and strict grounding prompts in `app/ai/guardrails.py`. Implement interaction logging to MySQL `chat_logs` in `app/utils/logging.py`.
- **Why**: Fulfills PRD security, auditing, and compliance requirements before exposing the system to end users.

### Stage 7: Reporting Engine (Excel Export)
- **What**: Implement Attendance, Overtime, and Leave export endpoints that generate downloadable `.xlsx` files using Pandas and OpenPyXL.
- **Why**: Fulfills PRD Section 22 reporting requirements.

### Stage 8: Frontend Web Application & Dashboard
- **What**: Build the web UI in `frontend/` (Login screen, Chat interface, Dashboard metrics cards, and attendance/leave charts).
- **Why**: Provides the final user-facing interface uniting the backend APIs and the conversational AI.

---

## 12. Important Technical Issues / Risks

### 1. Suspicious Dependency: `httpx2==2.13.1`
- `requirements.txt` contains `httpx2==2.13.1`. The standard and officially supported HTTP client for FastAPI/Python is `httpx` (which is also present in `.venv`). `httpx2` appears to be an unverified package or typosquat and should be reviewed or removed.

### 2. File Encoding Issue in `requirements.txt`
- `requirements.txt` is encoded in **UTF-16 LE** (likely generated via PowerShell redirection). Standard packaging tools, Docker builds, and automated CI pipelines often expect UTF-8 and fail when reading UTF-16 text files.

### 3. Missing `pytest` in `requirements.txt`
- While 16 integration test scripts exist in `tests/`, `pytest` is not listed in `requirements.txt` and is not installed in the virtual environment.

### 4. Incomplete `.env.example`
- `.env.example` only lists JWT configuration variables (`JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`). It lacks critical variables needed to run the project, including `DATABASE_URL`, LLM API keys (`GEMINI_API_KEY` / `OPENAI_API_KEY`), and Google OAuth credentials.

### 5. Misnamed File: `app/ai/lim.py`
- The file is named `lim.py` with an "i" instead of `llm.py` with an "l". It is currently an empty 0-byte file.

### 6. Misnamed File: `app/rag/retrievers.py`
- The PRD project structure specifies `retriever.py` (singular), while the repository contains `retrievers.py` (plural).

### 7. Zero-Byte Stub Files
- Several files exist only as empty 0-byte placeholders:
  - `app/api/chat.py`
  - `app/ai/guardrails.py`, `app/ai/lim.py`, `app/ai/prompts.py`, `app/ai/router.py`
  - `app/rag/chunker.py`, `app/rag/document_loader.py`, `app/rag/embeddings.py`, `app/rag/retrievers.py`
  - `app/services/attendance_service.py`, `app/services/leave_service.py`, `app/services/salary_service.py`
  - `app/utils/logging.py`
  - `README.md`
  - `test_database.py` (empty file in project root)

### 8. Import Path Bug in `tests/test_database.py`
- Line 2 of `tests/test_database.py` executes:
  ```python
  sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
  ```
  When run from the project root directory, this points to the parent folder (`projects/`) instead of the project root (`ai-hr-assistant/`), causing `ModuleNotFoundError: No module named 'app'` unless `PYTHONPATH=.` is explicitly provided.

### 9. Uncommitted Git Working State
- Working tree contains uncommitted changes:
  - `modified: app/api/salary.py` (added `GET /salary/{employee_id}`)
  - `untracked: tests/test_salary_get_by_id.py`

### 10. Weak Secret Key Length Warning in PyJWT
- During test execution, PyJWT emits `InsecureKeyLengthWarning: The HMAC key is 12 bytes long, which is below the minimum recommended length of 32 bytes for SHA256`. The development secret key should be at least 32 bytes (256 bits).

### 11. Code Duplication Risk (Direct DB Queries in Route Handlers)
- Route handlers currently embed SQL queries and calculations directly. If the upcoming AI tools query the database independently, business logic will be duplicated unless refactored into the service layer first.

---

## 13. Current Position

CURRENTLY WE ARE HERE:
Stage 2 (Database & Core HR REST APIs). Authentication, RBAC, and all primary REST endpoints for Employee Profile, Leaves, Attendance (with summary aggregations), and Salary (with employee isolation and HR lookup) are implemented and validated by 16 passing integration test suites (123 passing assertions).

NEXT LOGICAL TASK:
Refactor business calculations and database queries out of the API route handlers into dedicated service functions (`app/services/attendance_service.py`, `app/services/salary_service.py`, `app/services/leave_service.py`, and `app/database/queries.py`), and implement the remaining baseline PRD endpoints (`GET /employees`, `GET /employees/{id}`, `GET /leaves/{employee_id}`, `GET /salary/summary`).

WHY:
The upcoming AI layer (Router, Tool Calling, and Chat API) requires direct, programmatic access to attendance, leave, and salary calculations as Python callable functions, rather than making internal HTTP requests. Decoupling this business logic now establishes the exact toolset required for safe, controlled database querying by the AI agent.
