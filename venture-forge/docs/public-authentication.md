# Public authentication implementation

Public email/password registration extends the existing founder account. First-time Google and GitHub identities create a founder and enter the same Passport onboarding. Returning identities resolve by provider and immutable subject to their existing founder and venture history. No allowlist, invitation code, Google hosted-domain restriction, GitHub organization membership or pre-created founder is required by the application.

## Account and database mapping

| Requested concept | Existing implementation |
| --- | --- |
| users / user ID | `founders.id`, UUID stored as a 36-character string |
| display name | `founders.name` |
| email, avatar, onboarding, account status | `founders.email`, `avatar_url`, `onboarding_completed`, `is_active` |
| creation and last login | `founders.created_at`, `last_login_at` |
| email/password identity | nullable Argon2 `founders.password_hash`; OAuth-only users initially have none |
| auth identities / user relation | `oauth_identities.founder_id` references the existing founder |
| provider user ID | `oauth_identities.subject`: Google `sub` or GitHub integer ID as text |
| provider email / verification | `oauth_identities.email`, `email_verified` |
| provider profile and timestamps | `display_name`, `avatar_url`, `created_at`, `last_login_at` |
| sessions | existing `product_sessions`, with authentication time and method added |

`UNIQUE(provider, subject)` prevents the same external identity from belonging to two founders. `UNIQUE(founder_id, provider)` allows one identity from each provider per founder. An email/password founder can connect both providers. An OAuth founder can add password sign-in in Account Settings after a recent provider login. Matching provider email alone never links or replaces an existing account.

Migration **0006_public_authentication.py** extends the tables created by 0001/0005. It backfills onboarding from existing ventures, marks legacy verified provider identities accordingly, and preserves founders, passwords, identities, sessions and Passport records. Only pending OAuth attempts are invalidated because their stored callback format changes. It adds `auth_rate_limits` for atomic limits shared by all backend processes using the same database.

Apply with `python -m alembic upgrade head` before starting the updated API. The local launcher applies it automatically. Back up the database before migration or rollback. A downgrade removes the new metadata and disabled-account flag; perform it offline, restore from a tested backup when needed, and recheck account restrictions before reopening access. OAuth-only users remain unable to authenticate with a guessed password after a downgrade.

## HTTP routes

| Method and route | Behavior |
| --- | --- |
| `POST /api/v1/auth/register` | Name, email and password; creates founder and rotates session; 201 |
| `POST /api/v1/auth/login` | Existing password sign-in |
| `GET /api/v1/auth/oauth/google/start` | Browser redirect to Google authorization |
| `GET /api/v1/auth/oauth/google/callback` | Verified Google code exchange and application session |
| `GET /api/v1/auth/oauth/github/start` | Browser redirect to GitHub authorization |
| `GET /api/v1/auth/oauth/github/callback` | Verified GitHub code exchange and application session |
| `POST /api/v1/auth/oauth/{provider}/start` | Existing UI API, `mode=sign_in` or authenticated `mode=connect` |
| `GET /api/v1/auth/providers` | Public provider availability; no credentials |
| `GET /api/v1/auth/connections` | Authenticated connected accounts |
| `GET /api/v1/auth/password-status` | Authenticated password setup requirements |
| `POST /api/v1/auth/password` | Add/change password and revoke prior sessions |
| `GET /api/v1/auth/me` | Current active founder profile |
| `POST /api/v1/auth/logout` | Revoke current session and clear its cookie |

GET starts are for sign-in only. They reject cross-site browser initiation and extra query parameters; redirects always come from backend configuration. Linking uses the origin-protected POST and a state record bound to the initiating founder session. Callbacks redirect to the canonical application root, where the existing Passport loader selects onboarding or Venture Home.

## Sessions and error handling

Both providers use authorization codes, PKCE S256, and one-use browser-bound state with a ten-minute expiration. Google ID tokens are checked with PyJWT RS256 against Google's public keys, including issuer, audience, expiry, authorized party and nonce. Google requests only `openid email profile`; GitHub requests only `user:email` and reads a verified email. Profile URLs are accepted only as HTTPS URLs without embedded credentials.

The API stores only a SHA-256 digest of each random application session token. Cookies are HttpOnly, SameSite=Strict, Secure in production, host-scoped and expire after `SESSION_HOURS`. OAuth binding cookies use SameSite=Lax to support the return navigation. Success rotates the browser's initiating session even when the Strict cookie is absent from the callback. Logout removes its database session and pending connections. Password changes revoke all prior sessions and create a fresh one. No tokens or secrets are written to localStorage.

Authenticated operations and all sign-in methods check `founders.is_active`. Operators can disable an account through controlled database administration; there is no public administrative endpoint. Disabled accounts cannot use previously issued sessions. Revoke their session rows when disabling permanently to prevent reuse after a later re-enable.

Cancellation, invalid state, expired state, provider unavailability, unavailable/unverified email, email collision, callback mismatch, invalid response and disabled accounts have controlled error codes and user messages. Failure does not replace or clear the existing product session or modify a Passport. Upstream error descriptions and submitted passwords are not reflected in errors. Google may display a callback mismatch itself before returning to the application; in that case correct the console redirect URI.

Registration validates email syntax and uses a 15-128-character password without trimming it. Registration does not assert ownership of an email mailbox. Email verification delivery and forgotten-password recovery are not implemented in this change; provider verification remains independent and matching emails never silently merge accounts.

## Environment and deployment

Development:

```dotenv
APP_ENV=development
APP_ORIGIN=http://127.0.0.1:3000
COOKIE_SECURE=false
SESSION_HOURS=12
DATABASE_URL=<your-development-database-url>
GOOGLE_CLIENT_ID=<local-google-client-id>
GOOGLE_CLIENT_SECRET=<local-google-client-secret>
GITHUB_CLIENT_ID=<local-github-client-id>
GITHUB_CLIENT_SECRET=<local-github-client-secret>
```

Production:

```dotenv
APP_ENV=production
APP_ORIGIN=https://<production-domain>
COOKIE_SECURE=true
SESSION_HOURS=12
DATABASE_URL=<your-production-database-url>
GOOGLE_CLIENT_ID=<production-google-client-id>
GOOGLE_CLIENT_SECRET=<production-google-client-secret>
GITHUB_CLIENT_ID=<production-github-client-id>
GITHUB_CLIENT_SECRET=<production-github-client-secret>
```

Replace placeholders locally or in the hosting secret store. Never prefix OAuth secrets with `NEXT_PUBLIC_`. `.env` files are ignored; `.env.example` contains placeholders only. Existing local model-provider settings remain independent. `BOOTSTRAP_EMAIL` and `BOOTSTRAP_PASSWORD` are optional local/bootstrap tooling inputs, not a restriction on registration.

Build the frontend with `npm run build`, apply database migrations, and run the production Next.js server, API and worker under process supervision. Set server-side `FORGE_API_URL` to the API's private address if it differs from `http://127.0.0.1:8010`. Serve `/api/*` through the same HTTPS origin as the frontend. The Windows launcher is for local development and intentionally overrides production origin settings.

The API must be private behind the trusted proxy. Configure that proxy to replace untrusted forwarded headers and configure Uvicorn to trust only that proxy's addresses; the authentication limiter uses the resulting client IP, never arbitrary request-supplied headers. Verify distinct clients have distinct client IPs after deployment. Each authentication category permits ten attempts per IP per minute across workers and returns 429 with Retry-After. Apply hosting-level request/body/connection limits appropriate to public traffic. Strip OAuth callback query strings from proxy access logs, as the application already does for Uvicorn and Next development logs.

## Exact callback URLs and console steps

| Provider | Local | Production template |
| --- | --- | --- |
| Google | `http://127.0.0.1:3000/api/v1/auth/oauth/google/callback` | `https://<production-domain>/api/v1/auth/oauth/google/callback` |
| GitHub | `http://127.0.0.1:3000/api/v1/auth/oauth/github/callback` | `https://<production-domain>/api/v1/auth/oauth/github/callback` |

No production hostname has been supplied. Each production template is exactly `APP_ORIGIN` plus the provider's callback path; do not register the placeholder hostname. Local callbacks use the frontend's port 3000 through its API proxy, not the backend port.

1. Google: create/select the project, complete branding, select External audience, create a Web application client and register the exact callback. Testing mode can use your local test users. For public deployment, choose Publish app so status is In production; complete domain, branding, policy URL and verification requirements shown by Google. Use only the implemented identity scopes. [Google setup](https://developers.google.com/identity/openid-connect/openid-connect), [audience and production publishing](https://support.google.com/cloud/answer/15549945?hl=en).
2. GitHub: Settings > Developer settings > OAuth Apps > New OAuth App. Enter the application name, actual homepage and exact callback. Register, generate a secret, and store it server-side. Public users do not need to be pre-created in Venture Forge. [GitHub application registration](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
3. Use separate local/production credentials, restart the appropriate services and test a fresh provider account and an existing linked account. For existing Venture Forge users, sign in first and connect through Account Settings.

## Files changed

- Backend account/session schema: `backend/venture_forge/product/core/models.py`, `auth_models.py`, `schemas.py`.
- API routes: `backend/venture_forge/product/api/app.py`, `oauth.py`, new `public_auth.py`.
- Shared services: `backend/venture_forge/shared/auth.py`, `oauth.py`, `config.py`, new `auth_limits.py`.
- Migrations: new `database/migrations/versions/0006_public_authentication.py`; `0002_evidence_cycle.py` excludes the later rate-limit table on fresh installs.
- UI: `apps/web/components/ui/sign-in.tsx`, `sign-in.module.css`, `account-connections.tsx`, `apps/web/app/globals.css`, `apps/web/lib/auth.ts`.
- API contracts: regenerated `docs/openapi.json`, `apps/web/lib/contracts.ts`.
- Configuration/dependencies: `.env.example`, `pyproject.toml`, `requirements.lock`, `scripts/run_local.py`, parent `Start-VentureForge.ps1`.
- Tests: new `tests/test_public_auth.py`, new `tests/browser/public-auth.spec.ts`, updated `tests/test_oauth.py`, `scripts/browser_test_server.py`.
- Documentation: `README.md`, `docs/sign-in.md`, `docs/build-status.md`, this guide.

## Verification scope

Executed successfully on the completed implementation:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_auth.py tests/test_oauth.py tests/test_finance_tools.py tests/test_model_router.py tests/test_specialists.py tests/test_evidence_cycle.py --basetemp .local/pytest-public-verified --tb=short
# 123 passed; one upstream Starlette TestClient deprecation warning.
$env:FORGE_PORTABLE_TEST = '1'
npm run test:e2e
# 6 Chrome journeys passed.
npm run build
# Compilation, TypeScript checking and static generation passed.
```

The local database was backed up under `.local/backups/before-public-auth-0006.sqlite3`. After migration, original columns/rows in all 30 existing non-transient tables matched the pre-migration integrity manifest. Local API/web health, existing founder login, password settings, the thirteen-specialist catalog and logout were verified without displaying credentials. The local app is running at `http://127.0.0.1:3000`.

Backend tests use isolated SQLite databases, mocked provider HTTP and signed test Google JWTs. They cover public signup, returning identities, explicit links, state/replay/concurrency, collisions, disabled accounts, all callback failures, session rotation/revocation, password setup and exact Passport continuity. Migration tests exercise fresh installation, 0005 upgrades, metadata drift and rollback/reapplication while preserving account/identity/session/venture data.

The browser suite covers email registration, onboarding, password changes, sign-out and return to the same Passport, existing email login, mocked provider redirects, hydration, desktop/mobile layouts and the existing specialist pipelines. Real Google/GitHub credentials, an assigned production domain and production infrastructure are still required for a live provider/deployment test. SQLite results do not establish PostgreSQL deployment behavior.
