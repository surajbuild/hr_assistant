# AI HR Assistant — Backend

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
