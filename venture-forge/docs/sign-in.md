# Public email, Google and GitHub sign-in

The existing implementation uses the browser's Venture Forge origin for both callbacks. Next.js forwards `/api/*` to the Python API, which exchanges the authorization code and creates the founder session. Provider client secrets belong only in the backend environment.

Anyone can choose **Continue with email**, then **Create account**, and register with a name and a password of 15-128 characters. Google and GitHub automatically create an account for a first-time verified identity once their credentials are configured. There is no Venture Forge email allowlist or invitation requirement. New accounts see Passport onboarding; returning accounts see their existing Venture Home. See the [implementation and deployment guide](public-authentication.md) for the database mapping, routes, security behavior and file inventory.

## Exact local URLs

The local launcher runs the web application at **http://127.0.0.1:3000** and the API at port 8010. Register the callback URLs below on the **web origin**, because the browser returns through the Next.js API proxy.

| Setting | Value |
| --- | --- |
| Application homepage / local web origin | `http://127.0.0.1:3000` |
| Google authorized redirect URI | `http://127.0.0.1:3000/api/v1/auth/oauth/google/callback` |
| GitHub authorization callback URL | `http://127.0.0.1:3000/api/v1/auth/oauth/github/callback` |

These values come from `callback_uri()` in `backend/venture_forge/shared/oauth.py`, `APP_ORIGIN`, and `apps/web/next.config.ts`. Use the same hostname when opening the app: `localhost` and `127.0.0.1` are different origins. The current launcher uses port **3000**.

## Create the Google application

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or select your Venture Forge project.
2. Open **Google Auth Platform** and complete **Branding**: app name, support email, and developer contact email. If your console shows **OAuth consent screen**, begin there.
3. Under **Audience**, choose the users who can sign in. For an external app in testing, add your own Google account under **Test users**.
4. Open **Clients → Create client**, choose **Web application**, and name it `Venture Forge local`.
5. Under **Authorized redirect URIs**, add exactly:
   ```text
   http://127.0.0.1:3000/api/v1/auth/oauth/google/callback
   ```
6. The current server authorization-code flow does not use a browser Google SDK, so **Authorized JavaScript origins** is not required for this flow. If you populate that field, use `http://127.0.0.1:3000` without a path.
7. Create the client. Put its client ID and client secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `venture-forge/.env`.

The implementation requests `openid email profile`; it checks the signed ID token, audience, issuer, expiry, nonce and verified email. See Google's [OpenID Connect setup guide](https://developers.google.com/identity/openid-connect/openid-connect).

## Create the GitHub application

1. Open [GitHub Developer settings → OAuth Apps](https://github.com/settings/developers), then **New OAuth App**.
2. Set **Application name** to `Venture Forge local`.
3. Set **Homepage URL** to `http://127.0.0.1:3000`.
4. Set **Authorization callback URL** to exactly:
   ```text
   http://127.0.0.1:3000/api/v1/auth/oauth/github/callback
   ```
5. Select **Register application**.
6. Copy the client ID, generate a client secret, and place them in `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `venture-forge/.env`.

The implementation requests `user:email`, retrieves the authenticated GitHub account ID and selects a verified email. See GitHub's [OAuth authorization guide](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps) and [email endpoint documentation](https://docs.github.com/en/rest/users/emails#list-email-addresses-for-the-authenticated-user).

## Local environment and activation

The four fields are already present in your `.env`; fill their values locally:

```dotenv
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
APP_ENV=development
APP_ORIGIN=http://127.0.0.1:3000
COOKIE_SECURE=false
SESSION_HOURS=12
```

Keep the existing database settings and founder credentials. The repository already ignores `.env`, `.env.local` and other `.env.*` files, with `.env.example` as the deliberate template exception. Never place secrets in `NEXT_PUBLIC_*` variables or chat messages.

After saving the values, stop the running local launcher with **Ctrl+C**, then run **Start-VentureForge.ps1** again. Reopen `http://127.0.0.1:3000`. Each provider button becomes available when that provider's client ID and secret are present. Availability indicates configuration, not a completed provider login test.

For an existing founder account, sign in with email/password and open **Account settings → Connect Google / Connect GitHub**. Complete the provider prompt, then sign out and try its sign-in button. This connects the provider to the same saved Venture Passport. Matching email addresses are not linked automatically. First-time provider users with verified email receive a new founder account and the usual Passport onboarding.

## Production URLs

No production domain is configured in this workspace. The exact URL is generated from the deployed backend's `APP_ORIGIN`:

| Provider | Production callback pattern |
| --- | --- |
| Google | `{APP_ORIGIN}/api/v1/auth/oauth/google/callback` |
| GitHub | `{APP_ORIGIN}/api/v1/auth/oauth/github/callback` |

For example, **only if your deployed origin is** `https://forge.example.com`, the callbacks would be:

```text
https://forge.example.com/api/v1/auth/oauth/google/callback
https://forge.example.com/api/v1/auth/oauth/github/callback
```

Replace the example hostname with your actual deployed hostname before registration. Set `APP_ENV=production`, `APP_ORIGIN` to that HTTPS origin with no path, and `COOKIE_SECURE=true` in the production backend environment. Insecure production settings are rejected at startup. Serve the frontend and `/api/*` proxy on this same origin. The local launcher deliberately sets development and the loopback origin; use deployment configuration for production.

Create separate production OAuth applications/clients with these production callback URLs and production secrets. For Google, open **Google Auth Platform > Audience**, select **External**, and choose **Publish app** so publishing status is **In production**. Complete branding, authorized-domain and verification requirements shown by Google. Testing-mode test users are a console setting, not an application allowlist. Google Workspace or individual account policies can still restrict authorization. See Google's [audience and publishing documentation](https://support.google.com/cloud/answer/15549945?hl=en).

For GitHub, register a production OAuth App with the production homepage and callback URL. This application requests only `user:email`, with no repository or organization scopes. See [Creating an OAuth app](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app). Keep local credentials in the local `.env` and production credentials in your hosting environment's secret settings.

## Implementation and verification

Both providers support the requested GET start routes, which redirect to the provider. The existing UI retains origin-checked POST starts; explicit linking is POST-only. Both providers use PKCE S256 and a ten-minute, one-use state record bound to an HttpOnly browser cookie. Google additionally uses an OIDC nonce and RS256 signature verification. Provider tokens are used only on the backend and are not persisted or returned to the UI. Successful callbacks rotate the existing opaque HttpOnly founder session. Failed callbacks preserve the current product session and Passport. Callback authorization codes are omitted from the configured Next.js development request log and redacted from Uvicorn access logging; configure equivalent query-string redaction at any production proxy.

Migration `0005` added identities and state. Migration `0006` extends those records with verified provider profile data, login timestamps, account status, onboarding status, session authentication metadata and shared database rate limits. Founders, password hashes, linked identities, sessions and Passports are preserved. In-flight OAuth attempts must restart after migration. Account Settings can also add or change a password; adding one through a provider requires a provider login in the past ten minutes. Password changes revoke other sessions. Tests use synthetic identities, signed test JWTs, mocked provider HTTP and isolated databases; real provider sign-in still needs your configured applications.

The reported `crxlauncher` hydration warning comes from attributes inserted by the browser extension shown in the stack trace. The root `<html>` uses `suppressHydrationWarning`; child elements retain normal mismatch checking. This uses React's [single-element hydration escape hatch](https://react.dev/reference/react-dom/client/hydrateRoot#suppressing-unavoidable-hydration-mismatch-errors). A browser test injects the same root attributes before hydration and checks that sign-in loads without hydration errors.
