# Escalation Module - Beginner-Friendly Architecture & Walkthrough

This document explains each file created for the **Escalation Module** in clear, simple terms. Use this guide to easily defend and explain the design during team reviews.

---

## 1. File Breakdown (What each file does & Why)

### Configuration & Isolation
* [`.env.example`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/.env.example)
  * **What it does:** Provides a template of configuration values (database connection string, admin API key, SMTP email credentials, and rate limits).
  * **Why:** Keeps real passwords, secrets, and private keys off GitHub while giving team members a clear setup guide.

* [`.gitignore`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/.gitignore)
  * **What it does:** Tells Git to ignore sensitive `.env` files, virtual environments (`.venv/`), local SQLite databases (`*.db`, `*.sqlite`), and Node frontend folders (`node_modules/`, `dist/`).
  * **Why:** Prevents accidental leaks of credentials or committing multi-megabyte dependency folders.

* [`app/escalations/requirements.txt`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/requirements.txt)
  * **What it does:** Lists the exact pinned versions of Python libraries needed (FastAPI, SQLAlchemy, Pydantic, Alembic, Pytest, Ruff).
  * **Why:** Placed strictly inside `app/escalations/` (not at repo root) so it never causes merge conflicts when the team lead pushes the core backend requirements.

### Database & Data Models
* [`app/escalations/config.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/config.py)
  * **What it does:** Reads settings and environment variables safely using Pydantic v2 `pydantic-settings`.
  * **Why:** Centralizes all configuration (database URL, organizer admin token, email settings) with automatic type validation and default values.

* [`app/escalations/database.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/database.py)
  * **What it does:** Configures the SQLAlchemy database engine and provides `get_db()`, which opens and closes database sessions for API requests.
  * **Why:** Works with SQLite out-of-the-box for local testing, yet fully supports PostgreSQL for production; designed so the team lead can easily point it to their shared database session.

* [`app/escalations/models.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/models.py)
  * **What it does:** Defines the `Escalation` database table and a helper function `generate_reference_id()` that creates IDs like `ESC-7K3F9Q` using Python's `secrets` module.
  * **Why:** Stores escalation tickets safely, avoids confusing characters like `0`/`O` and `1`/`I`, and hides personal contact details and question text inside `__repr__` so logs never leak attendee data.

* [`app/escalations/migrations/0001_create_escalations_table.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/migrations/0001_create_escalations_table.py)
  * **What it does:** An Alembic migration script that creates the `escalations` table and database indexes.
  * **Why:** Self-contained and decoupled so the lead can drop it straight into `app/db/migrations/versions/` when ready.

### Validation, Security & Business Logic
* [`app/escalations/schemas.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/schemas.py)
  * **What it does:** Defines the shapes and validation rules for JSON requests and responses using Pydantic v2.
  * **Why:** Automatically checks question length (5 to 2000 characters) and enforces privacy: if an attendee submits contact info but doesn't check "wants follow-up", the contact info is automatically wiped to protect attendee privacy.

* [`app/escalations/dependencies.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/dependencies.py)
  * **What it does:** Verifies that requests to `/v1/admin/*` provide the correct organizer API key or token in the `Authorization` header.
  * **Why:** Keeps admin security checks in a single function so the team can later swap it with the official website authentication without editing individual endpoints.

* [`app/escalations/rate_limiter.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/rate_limiter.py)
  * **What it does:** Tracks client IP addresses and enforces a sliding-window limit (default 5 requests/minute) on public question submissions.
  * **Why:** Shields the system from spam bots or denial-of-service attempts by returning HTTP 429 with a clear `Retry-After` header.

* [`app/escalations/email_service.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/email_service.py)
  * **What it does:** An email dispatch interface with a real SMTP sender (`SMTPEmailService`) and an in-memory fake sender (`MockEmailService`).
  * **Why:** Decouples email logic from business logic so tests can run instantly offline without needing a real SMTP server.

* [`app/escalations/service.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/service.py)
  * **What it does:** Contains the core business logic (saving escalations, scheduling background emails, recording answers, and approving FAQ items).
  * **Why:** Keeps background email dispatches non-blocking and safe: even if an SMTP server is down, the escalation is still safely stored with `email_status="failed"` and the error details preserved.

* [`app/escalations/router.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/app/escalations/router.py)
  * **What it does:** Maps the web URLs (`POST /v1/escalations`, `GET /v1/admin/escalations`, retry, answer, and FAQ approval) to their corresponding functions.
  * **Why:** Packages the entire module into a single FastAPI `router` that the lead can mount in their main app with one line of code: `app.include_router(escalations_router)`.

### Local Execution & Testing
* [`scripts/dev_escalations_app.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/scripts/dev_escalations_app.py)
  * **What it does:** A lightweight FastAPI server for local development that mounts the router, enables CORS for the React dashboard, and formats errors into `{code, message, request_id, retry_after_seconds}`.
  * **Why:** Lets us run and demo the full escalation system and dashboard locally without needing the lead's main application files.

* [`tests/escalations/conftest.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/tests/escalations/conftest.py)
  * **What it does:** Prepares test fixtures: an in-memory SQLite database, clean session management, and a mock email service.
  * **Why:** Ensures test isolation so tests run rapidly in memory without touching real databases or networks.

* [`tests/escalations/test_escalations.py`](file:///c:/Users/KIIT/Desktop/AWS-chatbot-/tests/escalations/test_escalations.py)
  * **What it does:** 10 automated test cases proving all functional and privacy rules work.
  * **Why:** Proves that anonymous questions work, contacts are only kept with consent, email failures never lose data, sensitive questions cannot be approved for FAQ (409), unauthorized callers are blocked (401), logs stay clean of PII, and rate limits work (429).

---

## 2. How to Run (Windows PowerShell)

> [!IMPORTANT]
> Because you are on Windows PowerShell, run commands separately or use `;` (do NOT use `&&`).

### Step A: Setup Virtual Environment & Install Dependencies
```powershell
# 1. Activate or create your virtual environment (if not already done)
.\.venv\Scripts\Activate.ps1

# 2. Install pinned dependencies
pip install -r app/escalations/requirements.txt
```

### Step B: Run Automated Tests
```powershell
# Run the complete test suite with detailed output
python -m pytest -v tests/escalations/
```

### Step C: Run Local Backend Server
```powershell
# Starts the development server at http://127.0.0.1:8000
python scripts/dev_escalations_app.py
```
* **Interactive API Documentation (Swagger):** `http://127.0.0.1:8000/docs`

### Step D: Run Code Linter (Ruff)
```powershell
# Verify formatting and code quality
python -m ruff check .
```

---

## 3. Privacy & Safety Summary for Review
1. **Consent-Gated Contact Storage:** Contact info is stripped to `None` unless `wants_followup` is explicitly `True`.
2. **Crash-Resistant Email Fallback:** Email notifications run in background tasks. Even if the SMTP server is completely unreachable, the attendee's question is safely committed to the database with `email_status="failed"` and the error details recorded for manual retry.
3. **No PII in Application Logs:** Models and services sanitize logs to ensure participant emails and private queries never enter server logs or exception traces.
4. **FAQ Safeguard:** Personal or sensitive questions (`is_personal=True`) are blocked with HTTP `409 Conflict` from being approved for public FAQs.
