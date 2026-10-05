"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Founder } from "@/lib/api";
import { providerDefaults, startProviderSignIn, type AuthProviders, type ProviderId } from "@/lib/auth";
import { ProviderIcon } from "./provider-icon";

type PasswordStatus = { email: string; enabled: boolean; requires_current: boolean; requires_reauthentication: boolean };

export function AccountConnections({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [providers, setProviders] = useState(providerDefaults);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<ProviderId | "password" | null>(null);
  const [error, setError] = useState("");
  const [passwordStatus, setPasswordStatus] = useState<PasswordStatus | null>(null);
  const [password, setPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [notice, setNotice] = useState("");
  const starting = useRef(false);

  useEffect(() => {
    dialog.current?.showModal();
    let active = true;
    Promise.all([api<AuthProviders>("/auth/connections"), api<PasswordStatus>("/auth/password-status")])
      .then(([connections, status]) => { if (active) { setProviders(connections.providers); setPasswordStatus(status); } })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Couldn't load your connections."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function connect(provider: ProviderId) {
    if (starting.current) return;
    starting.current = true;
    setBusy(provider); setError("");
    try { await startProviderSignIn(provider, "connect"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't connect your account."); setBusy(null); starting.current = false; }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (starting.current) return;
    starting.current = true; setBusy("password"); setError(""); setNotice("");
    try {
      const founder = await api<Founder>("/auth/password", { method: "POST", body: JSON.stringify({ password, current_password: currentPassword || null }) });
      setPasswordStatus({ email: founder.email, enabled: true, requires_current: true, requires_reauthentication: false });
      setPassword(""); setCurrentPassword("");
      setNotice("Password saved. Your other sessions have been signed out.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't save your password."); }
    finally { starting.current = false; setBusy(null); }
  }

  return <dialog ref={dialog} className="account-connections" aria-labelledby="account-title" onCancel={onClose}>
    <div className="section-top"><h2 id="account-title">Account settings</h2><button className="icon-button" type="button" aria-label="Close account settings" onClick={onClose}>×</button></div>
    <p>Connect an account to sign in to this founder workspace with Google or GitHub.</p>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="connection-list" aria-busy={loading || busy !== null}>{providers.map(provider => <article key={provider.id}>
      <ProviderIcon provider={provider.id} /><div><strong>{provider.label}</strong><small>{provider.connected ? provider.email : provider.available ? "Ready to connect" : "Not available yet"}</small></div>
      <button className="button secondary" type="button" disabled={loading || busy !== null || !provider.available || provider.connected} onClick={() => void connect(provider.id)}>{busy === provider.id ? "Connecting…" : provider.connected ? "Connected" : `Connect ${provider.label}`}</button>
    </article>)}</div>
    {passwordStatus && <details className="account-password">
      <summary>{passwordStatus.enabled ? "Change password" : "Add email and password sign-in"}</summary>
      <p>Sign in with {passwordStatus.email} and your password.</p>
      {passwordStatus.requires_reauthentication ? <p>Sign out and sign in with your connected provider again before adding a password.</p> : <form onSubmit={savePassword}>
        <fieldset disabled={busy !== null}>
          {passwordStatus.requires_current && <label>Current password<input type="password" autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} required maxLength={256} /></label>}
          <label>New password<input type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} required minLength={15} maxLength={128} aria-describedby="account-password-hint" /></label>
          <p id="account-password-hint">Use at least 15 characters.</p>
          <button type="submit" className="button secondary">{busy === "password" ? "Saving password…" : "Save password"}</button>
        </fieldset>
      </form>}
    </details>}
    {notice && <p role="status">{notice}</p>}
    <p className="account-note">Your connected accounts open the same Venture Passport.</p>
  </dialog>;
}
