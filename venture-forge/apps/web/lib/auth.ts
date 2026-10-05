import { api } from "./api";

export type ProviderId = "google" | "github";
export type AuthProvider = { id: ProviderId; label: string; available: boolean; connected: boolean; email: string | null };
export type AuthProviders = { providers: AuthProvider[] };

export const providerDefaults: AuthProvider[] = [
  { id: "google", label: "Google", available: false, connected: false, email: null },
  { id: "github", label: "GitHub", available: false, connected: false, email: null },
];

const returnErrors: Record<string, string> = {
  cancelled: "Sign-in was cancelled. Choose a sign-in option to try again.",
  invalid_state: "This sign-in link expired or belongs to another browser. Please start again.",
  expired_state: "This sign-in request expired. Please start again.",
  provider_unavailable: "This sign-in provider is unavailable. Try again later or continue with email.",
  email_unavailable: "Your provider did not return an email address. Add a verified email to that account and try again.",
  callback_mismatch: "The provider return address does not match this Venture Forge environment. Contact the site administrator.",
  invalid_provider_response: "We couldn't verify the provider's response. Please start sign-in again.",
  account_disabled: "This Venture Forge account is disabled. Contact support.",
  unverified_email: "Your provider account needs a verified email address before you can sign in.",
  account_exists: "An account already uses this email. Sign in with your password, then connect the provider in Account settings.",
  provider_failed: "The provider couldn't complete sign-in. Please try again or use your email and password.",
  link_session_expired: "Your workspace session expired while connecting the account. Sign in and try again.",
  identity_in_use: "This provider account is already connected to another founder workspace.",
  already_connected: "A different account from this provider is already connected to your workspace.",
  account_conflict: "This account was changed during sign-in. Please start again.",
};

export function readAuthReturn(): { error?: string; connected?: string } | null {
  const url = new URL(window.location.href);
  const error = url.searchParams.get("auth_error");
  const connected = url.searchParams.get("auth_connected");
  if (!error && !connected) return null;
  url.searchParams.delete("auth_error");
  url.searchParams.delete("auth_connected");
  window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  if (error) return { error: returnErrors[error] || returnErrors.provider_failed };
  if (connected === "google" || connected === "github") return { connected: connected === "google" ? "Google" : "GitHub" };
  return null;
}

export async function startProviderSignIn(provider: ProviderId, mode: "sign_in" | "connect" = "sign_in") {
  const result = await api<{ authorization_url: string }>(`/auth/oauth/${provider}/start`, { method: "POST", body: JSON.stringify({ mode }), signal: AbortSignal.timeout(30000) });
  window.location.assign(result.authorization_url);
}
