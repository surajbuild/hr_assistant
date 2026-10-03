# AI HR Assistant — Backend.

FastAPI backend for an AI-powered HR Assistant managing employees, attendance, leaves, payroll, and authentication.

---

## Authentication Architecture

The backend supports two authentication mechanisms that issue the same application JWT:

1. **Email + Password**: `POST /auth/login`
2. **Google OAuth 2.0 / OIDC**:
   - `GET /auth/google/login`: Redirects user to Google's consent screen with CSRF state protection.
   - `GET /auth/google/callback`: Validates identity claims, links or provisions the local user, and returns an application JWT.

All protected API endpoints require:
```
Authorization: Bearer <access_token>
```

---

## Google Cloud Console OAuth 2.0 Setup

To enable Google login in local development:

1. **Open Google Cloud Console**:
   Navigate to [Google Cloud Console](https://console.cloud.google.com/).
2. **Create or Select a Project**:
   Create a new project (e.g., `ai-hr-assistant-dev`).
3. **Configure OAuth Consent Screen**:
   - User Type: **External**
   - App Name: `AI HR Assistant`
   - User support email & Developer contact info: your email
   - Scopes: `openid`, `email`, `profile`
   - Test users: add your test Google account email.
4. **Create OAuth 2.0 Client Credentials**:
   - Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**.
   - Application type: **Web application**.
   - Name: `AI HR Assistant Web Client`.
   - **Authorized JavaScript origins**:
     - `http://localhost:8000`
   - **Authorized redirect URIs**:
     - `http://localhost:8000/auth/google/callback`
5. **Set Environment Variables**:
   Copy the generated Client ID and Client Secret into your local `.env`:
   ```bash
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   SESSION_SECRET_KEY=a-secure-random-session-secret-key
   ```

---

## Running Locally

1. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run migrations:
   ```bash
   alembic upgrade head
   ```
4. Start the server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
5. Test Google Login:
   Visit `http://localhost:8000/auth/google/login` in your browser.

## Understand the repo
   You are working on an existing GitHub repository that has been cloned locally but is not yet fully completed.

Your first task is to **fully understand and audit the repository before making any code changes**.

Do NOT implement, refactor, delete, rename, or modify anything yet.

## 1. Understand the repository

First inspect the entire project structure and identify:

* Frontend
* Backend
* Database
* API layer
* Authentication/authorization
* AI/LLM components, if any
* Configuration/environment files
* Testing setup
* Build/deployment setup
* Documentation
* Scripts and tooling
* External services/dependencies

Read the important source files rather than only looking at filenames.

## 2. Understand the intended product

Determine from the existing code, README, documentation, comments, routes, schemas, UI, tests, and configuration:

* What this project is supposed to do
* Who the intended users are
* Main features
* Current user flows
* Expected architecture
* Technologies being used
* What appears to be already implemented
* What appears to be partially implemented
* What appears to be missing

Do not assume that something is required unless there is evidence in the repository or documentation. Clearly label assumptions.

## 3. Find incomplete work

Identify all signs of unfinished development, including:

* TODOs
* FIXME comments
* Placeholder UI
* Mock data
* Hardcoded values
* Dummy APIs
* Unused files/components
* Incomplete routes
* Missing error handling
* Missing validation
* Broken imports
* Dead code
* Temporary implementations
* Features referenced in documentation but not implemented
* Backend functionality without frontend integration
* Frontend functionality without backend support
* Database models without corresponding operations
* APIs without tests
* Tests for functionality that does not yet exist

For each item, explain what is missing and where it is located.

## 4. Check the project technically

Inspect the project for:

### Frontend

* Build errors
* TypeScript errors
* ESLint issues
* Routing problems
* State-management issues
* API integration issues
* Loading/error/empty states
* Responsive UI issues
* Accessibility issues
* Performance concerns

### Backend

* API correctness
* Validation
* Error handling
* Database queries
* Service-layer structure
* Security issues
* Authorization/RBAC
* Missing edge-case handling
* Configuration problems

### Database

* Schema/model quality
* Relationships
* Indexes
* Constraints
* Missing migrations/seeding
* Data consistency concerns

### Testing

Determine:

* What test framework is being used
* What is already covered
* What is not covered
* Whether tests actually run
* Whether important user flows have tests
* Whether integration/end-to-end tests are missing

### Deployment

Check:

* Environment variables
* Production configuration
* Build commands
* Start commands
* Docker configuration, if present
* CI/CD, if present
* Deployment assumptions
* Production-only risks

## 5. Verify instead of guessing

Run safe, read-only verification commands where appropriate.

Examples:

* Install/check dependencies if already configured
* Run existing tests
* Run type checking
* Run linting
* Run production build
* Inspect package scripts
* Inspect configuration

Do NOT change project files just to make the checks pass.

Record the actual results.

## 6. Create a gap analysis

Create a clear table with these columns:

| Area | Current State | Missing/Problem | Evidence/File | Priority |
| ---- | ------------- | --------------- | ------------- | -------- |

Use these priority levels:

* Critical
* High
* Medium
* Low

Priority should be based on practical impact, not personal preference.

## 7. Create the development roadmap

After understanding the repository, create a roadmap in the correct dependency order.

Separate it into:

### Phase 0 — Setup / Stabilization

Anything required before development can proceed reliably.

### Phase 1 — Critical missing functionality

Features or fixes required for the core product to work.

### Phase 2 — Complete major features

Remaining functional requirements.

### Phase 3 — Testing and reliability

Unit, integration, API, and end-to-end coverage.

### Phase 4 — UI/UX and performance

Only after core functionality is stable.

### Phase 5 — Production readiness

Security, deployment, monitoring, error handling, documentation, etc.

For every task include:

* Task name
* Why it is needed
* Files/components likely involved
* Dependencies on other tasks
* Verification method
* Priority

## 8. Identify the recommended development order

At the end, give me:

**A. What is already working**

**B. What is partially working**

**C. What is completely missing**

**D. What is broken**

**E. What should NOT be changed yet**

**F. The exact recommended order in which I should work**

The development order should minimize unnecessary rework and respect dependencies.

## 9. Define the first task

Do not start implementing the whole roadmap.

Instead, identify the **single best first task** to work on.

For that first task provide:

* Objective
* Current problem
* Expected outcome
* Files involved
* Acceptance criteria
* Tests/checks that should pass afterward

The acceptance criteria must be concrete and testable.

## Important rules

1. Do not modify any files during this audit.
2. Do not rewrite working code just because you prefer another architecture.
3. Preserve the existing technology stack unless there is a clear repository-based reason to change it.
4. Distinguish facts from assumptions.
5. Reference exact files, folders, routes, components, models, and configuration when possible.
6. Do not recommend adding technology just for the sake of adding it.
7. Prefer completing and stabilizing existing functionality before introducing new features.
8. Do not start implementing until the audit and roadmap are complete.

At the end, give me a concise **"PROJECT STATUS REPORT"** containing:

1. Project purpose
2. Current architecture
3. Working features
4. Incomplete features
5. Bugs/problems
6. Missing requirements
7. Technical debt
8. Testing status
9. Production-readiness status
10. Recommended roadmap
11. First task to implement

