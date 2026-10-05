"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, type Founder } from "@/lib/api";
import styles from "./sign-in.module.css";
import { providerDefaults, startProviderSignIn, type AuthProviders, type ProviderId } from "@/lib/auth";
import { ProviderIcon } from "./provider-icon";

function AuthIcon({ name }: { name: "mail" | "lock" | "eye" | "eye-off" | "arrow" | "back" | "alert" }) {
  const shapes: Record<typeof name, ReactNode> = {
    mail: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m3 7 9 6 9-6" /></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" /></>,
    eye: <><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></>,
    "eye-off": <><path d="m3 3 18 18M10.6 5.1 12 5c7 0 10 7 10 7a18 18 0 0 1-3 4m-2.5 2.1A10 10 0 0 1 12 19c-7 0-10-7-10-7a18 18 0 0 1 4-4.8m4 2.8a3 3 0 0 0 4 4" /></>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    back: <path d="M19 12H5m5-5-5 5 5 5" />,
    alert: <><circle cx="12" cy="12" r="9" /><path d="M12 7v6m0 3v.1" /></>,
  };
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

function GradientBackground() {
  return <div className={styles.background} aria-hidden="true">
    <svg width="100%" height="100%" viewBox="0 0 800 600" fill="none" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id="forge-auth-green" x1="0%" y1="0%" x2="100%" y2="100%"><stop stopColor="#c1d9c5" /><stop offset="1" stopColor="#9dbdb5" /></linearGradient>
        <linearGradient id="forge-auth-lilac" x1="0%" y1="0%" x2="100%" y2="100%"><stop stopColor="#e6d9ed" /><stop offset="1" stopColor="#bdcce1" /></linearGradient>
        <radialGradient id="forge-auth-peach"><stop stopColor="#eed7bf" /><stop offset="1" stopColor="#eee3dc" /></radialGradient>
        <filter id="forge-auth-blur" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="45" /></filter>
      </defs>
      <g className={styles.floatOne} filter="url(#forge-auth-blur)">
        <ellipse cx="80" cy="510" rx="340" ry="200" fill="url(#forge-auth-green)" transform="rotate(-25 80 510)" />
        <rect x="550" y="-80" width="370" height="350" rx="150" fill="url(#forge-auth-lilac)" transform="rotate(15 650 100)" />
      </g>
      <g className={styles.floatTwo} filter="url(#forge-auth-blur)">
        <circle cx="730" cy="570" r="210" fill="url(#forge-auth-peach)" />
        <ellipse cx="20" cy="10" rx="230" ry="180" fill="#e5e9d7" />
      </g>
    </svg>
  </div>;
}

/** Glass authentication design adapted to the existing founder session API. */
export function AuthComponent({ onSuccess, initialError = "" }: { onSuccess: () => Promise<void>; initialError?: string }) {
  const [step, setStep] = useState<"email" | "password">("email");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [providers, setProviders] = useState(providerDefaults);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [openingProvider, setOpeningProvider] = useState<ProviderId | null>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const previousStep = useRef(step);

  useEffect(() => {
    let active = true;
    api<AuthProviders>("/auth/providers")
      .then(result => { if (active) setProviders(result.providers); })
      .catch(() => { if (active) setProviders(providerDefaults); })
      .finally(() => { if (active) setProvidersLoading(false); });
    return () => { active = false; };
  }, []);

  async function signInWithProvider(provider: ProviderId) {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true); setOpeningProvider(provider); setError("");
    try { await startProviderSignIn(provider); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't open provider sign-in."); submitting.current = false; setOpeningProvider(null); setBusy(false); }
  }

  useEffect(() => {
    if (previousStep.current === step) return;
    previousStep.current = step;
    (step === "password" ? passwordRef : emailRef).current?.focus();
  }, [step]);

  useEffect(() => {
    if (mode === "register") nameRef.current?.focus();
  }, [mode]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setError("");
    if (step === "email") {
      setEmail(email.trim());
      setStep("password");
      return;
    }
    submitting.current = true;
    setBusy(true);
    try {
      await api<Founder>(`/auth/${mode}`, { method: "POST", body: JSON.stringify(mode === "register" ? { email, password, name: name.trim() } : { email, password }) });
      setPassword("");
      await onSuccess();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-in failed. Please try again.");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function goBack() {
    setStep("email");
    setPassword("");
    setShowPassword(false);
    setError("");
  }

  function chooseMode(value: "login" | "register") {
    setMode(value);
    setPassword("");
    setShowPassword(false);
    setError("");
  }

  return <main className={styles.page}>
    <GradientBackground />
    <header className={styles.header}>
      <a className={styles.brand} href="/" aria-label="Venture Forge home">
        <span className={styles.brandMark} aria-hidden="true"><span className="mark"><i /><i /><i /></span></span>
        <span>venture<span className={styles.brandLight}>forge</span></span>
      </a>
      <span className={styles.headerNote}>FROM POSSIBILITY TO PROOF</span>
    </header>

    <section className={styles.content} aria-labelledby="sign-in-title">
      <div className={styles.intro}>
        <span className={styles.eyebrow}><span />YOUR FOUNDER WORKSPACE</span>
        <h1 id="sign-in-title">Welcome to the Forge.</h1>
        <p>Your next chapter starts with a better question.</p>
      </div>

      <form onSubmit={submit} className={styles.form} aria-busy={busy}>
        <fieldset disabled={busy}>
          <label htmlFor="founder-email" className={styles.label}>Email address</label>
          <div className={`${styles.inputShell} ${step === "password" ? styles.savedEmail : ""}`}>
            <AuthIcon name="mail" />
            <input ref={emailRef} id="founder-email" name="email" type="email" autoComplete="username" placeholder="you@example.com" value={email} onChange={event => { setEmail(event.target.value); setError(""); }} readOnly={step === "password"} required maxLength={254} spellCheck={false} autoCapitalize="none" aria-describedby={error ? "sign-in-error" : undefined} />
            {step === "email" && <button className={styles.iconButton} type="submit" aria-label="Continue to password"><AuthIcon name="arrow" /></button>}
            {step === "password" && <span className={styles.emailBadge}>You</span>}
          </div>

          {step === "password" && <div className={styles.passwordStep}>
            <div className={styles.modeButtons} aria-label="Email account options">
              <button type="button" aria-pressed={mode === "login"} onClick={() => chooseMode("login")}>Sign in</button>
              <button type="button" aria-pressed={mode === "register"} onClick={() => chooseMode("register")}>Create account</button>
            </div>
            {mode === "register" && <div className={styles.nameField}>
              <label htmlFor="founder-name" className={styles.label}>Your name</label>
              <div className={styles.inputShell}><input ref={nameRef} id="founder-name" name="name" autoComplete="name" placeholder="Your name" value={name} onChange={event => setName(event.target.value)} required maxLength={100} /></div>
            </div>}
            <label htmlFor="founder-password" className={styles.label}>Password</label>
            <div className={styles.inputShell}>
              <AuthIcon name="lock" />
              <input ref={passwordRef} id="founder-password" name="password" type={showPassword ? "text" : "password"} autoComplete={mode === "register" ? "new-password" : "current-password"} placeholder={mode === "register" ? "Create a password" : "Enter your password"} value={password} onChange={event => { setPassword(event.target.value); setError(""); }} required minLength={mode === "register" ? 15 : 1} maxLength={mode === "register" ? 128 : 256} aria-describedby={[error && "sign-in-error", mode === "register" && "password-guidance"].filter(Boolean).join(" ") || undefined} />
              <button className={`${styles.iconButton} ${styles.visibilityButton}`} type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}><AuthIcon name={showPassword ? "eye-off" : "eye"} /></button>
            </div>
            {mode === "register" && <p id="password-guidance" className={styles.passwordGuidance}>Use at least 15 characters. A memorable passphrase works well.</p>}
          </div>}

          {error && <p id="sign-in-error" className={styles.error} role="alert"><AuthIcon name="alert" /><span>{error}</span></p>}

          <button className={styles.glassButton} type="submit">
            {busy ? <><span className={styles.spinner} aria-hidden="true" />{openingProvider ? `Opening ${openingProvider === "google" ? "Google" : "GitHub"}…` : mode === "register" ? "Creating your account…" : "Signing in…"}</> : <>{step === "email" ? "Continue with email" : mode === "register" ? "Create your account" : "Enter your workspace"}<AuthIcon name="arrow" /></>}
          </button>

          {step === "password" && <button className={styles.backButton} type="button" onClick={goBack}><AuthIcon name="back" />Use a different email</button>}

          {step === "email" && <div className={styles.socialSection}>
            <div className={styles.divider}><span />Other sign-in options<span /></div>
            <div className={styles.socialButtons}>
              {providers.map(provider => <button
                key={provider.id}
                type="button"
                className={styles.socialButton}
                disabled={providersLoading || !provider.available}
                title={!providersLoading && !provider.available ? `${provider.label} sign-in is not available yet` : undefined}
                onClick={() => void signInWithProvider(provider.id)}
              ><ProviderIcon provider={provider.id} /><span>Sign in with {provider.label}</span></button>)}
            </div>
          </div>}
        </fieldset>
        <p className={styles.status} role="status">{busy ? openingProvider ? "Opening secure provider sign-in…" : mode === "register" ? "Creating your founder workspace…" : "Checking your credentials securely…" : step === "password" ? mode === "register" ? "Your own space to turn questions into evidence." : "Sign in or create your founder account." : ""}</p>
        <p className={styles.terms}>By continuing, you agree to our Terms of Service and Privacy Policy.</p>
      </form>
    </section>

    <footer className={styles.footer}><span>Build with intention.</span><span className={styles.privacy}><AuthIcon name="lock" />A private space for your next move.</span></footer>
  </main>;
}
