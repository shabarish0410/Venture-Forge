"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ToolPanel, toolNames, records, type Tool } from "./tools";
import { Pipelines, agentRecords } from "./agents";
import { AuthComponent } from "@/components/ui/sign-in";
import { AccountConnections } from "@/components/ui/account-connections";
import { readAuthReturn } from "@/lib/auth";
import { api, ApiError, type Founder, type Passport, type VentureCreate, type HypothesisCreate } from "@/lib/api";

type View = Tool | "hypotheses" | "activity" | "pipelines";
const labels: Record<View, string> = { ...toolNames, pipelines: "Agent Pipelines", hypotheses: "Hypotheses", activity: "Activity" };

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const shapes: Record<string, React.ReactNode> = {
    home: <><path d="m3 10 9-7 9 7v10H3Z"/><path d="M9 20v-7h6v7"/></>,
    passport: <><rect x="4" y="3" width="16" height="18" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M8 17h8M2 7h4M2 12h4M2 17h4"/></>,
    hypotheses: <><path d="M9 18h6m-6 3h6M8 14a7 7 0 1 1 8 0l-1 4H9Z"/><path d="M10 9h4m-2-2v4"/></>,
    activity: <><path d="M3 12h4l3-8 4 16 3-8h4"/></>,
    arrow: <><path d="M5 12h14m-5-5 5 5-5 5"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    exit: <><path d="M9 4H4v16h5m6-12 4 4-4 4m-7-4h11"/></>,
    company: <><path d="M3 21V6l9-3v18m0-12h9v12M7 8v1m0 4v1m0 4v1m9-6v1m0 4v1"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    research: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6m-3-3v6"/></>,
    customer: <><circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m0-16a3 3 0 0 1 0 6m3 3a5 5 0 0 1 3 5v2"/></>,
    experiment: <><path d="M9 3h6m-5 0v7L4 20h16l-6-10V3M7 15h10"/></>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name] || shapes.home}</svg>;
}

function Mark() { return <span className="mark" aria-hidden="true"><i/><i/><i/></span>; }
function ErrorNotice({ message }: { message: string }) { return message ? <p className="error" role="alert">{message}</p> : null; }
function date(value: string) { return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }).format(new Date(value)); }

export default function Workspace() {
  const [founder, setFounder] = useState<Founder | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("home");
  const [showAdd, setShowAdd] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [authNotice, setAuthNotice] = useState<{ error?: string; connected?: string } | null>(null);

  const model = passport ? records(passport).artifacts.filter(a => a.capability === "model" && a.status === "ACCEPTED").at(-1) : null;
  const modelFields = (model?.result.data as Record<string, unknown> | undefined)?.fields || model?.result.fields;
  const buyer = String((modelFields as Record<string, unknown> | undefined)?.Buyer || "unknown");

  async function restore() {
    setError(""); setLoading(true);
    try {
      const profile = await api<Founder>("/auth/me");
      const result = await api<{ ventures: { id: string }[] }>("/ventures");
      const saved = result.ventures.length ? await api<Passport>(`/ventures/${result.ventures[0].id}/passport`) : null;
      setFounder(profile); setPassport(saved);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { setFounder(null); setPassport(null); }
      else setError(e instanceof Error ? e.message : "Couldn't open your workspace.");
    } finally { setLoading(false); }
  }
  useEffect(() => { const notice = readAuthReturn(); if (notice) setAuthNotice(notice); void restore(); }, []);
  useEffect(() => {
    if (!passport || !agentRecords(passport).agent_runs.some(r => ["QUEUED", "RUNNING"].includes(r.status))) return;
    let active = true;
    const timer = setInterval(() => {
      api<Passport>(`/ventures/${passport.venture.id}/passport`).then(p => { if (active) setPassport(p); }).catch(e => { if (active) setError(e.message); });
    }, 1500);
    return () => { active = false; clearInterval(timer); };
  }, [passport]);

  async function signOut() {
    try { await api("/auth/logout", { method: "POST" }); setFounder(null); setPassport(null); setView("home"); setShowAccount(false); setAuthNotice(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Sign-out failed."); }
  }

  function exportPassport() {
    if (!passport) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(passport, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "venture-passport.json"; link.click();
    URL.revokeObjectURL(url);
  }

  if (loading) return <div className="loading"><Mark/><p>Opening your workspace…</p></div>;
  if (error && !founder) return <div className="loading"><h1>Let’s reconnect.</h1><ErrorNotice message={error}/><button className="button primary" onClick={() => void restore()}>Try again</button></div>;
  if (!founder) return <AuthComponent initialError={authNotice?.error} onSuccess={async () => { setAuthNotice(null); await restore(); }}/>;

  return <div className="workspace">
    <a href="#main" className="skip-link">Skip to content</a>
    <aside className="sidebar">
      <a href="/" className="brand" aria-label="Venture Forge home"><Mark/><span>venture<span className="brand-light">forge</span><small>FROM POSSIBILITY TO PROOF</small></span></a>
      <div className="workspace-label"><span className="tiny-dot"/> FOUNDER WORKSPACE</div>
      <nav aria-label="Product workspace">{(Object.keys(labels) as View[]).map(key => <button key={key} title={labels[key]} className={`nav-item ${view === key ? "active" : ""}`} aria-current={view === key ? "page" : undefined} onClick={() => setView(key)}><Icon name={key === "experiment" ? "experiment" : ["finance", "market", "simulation", "model"].includes(key) ? "activity" : ["competitor", "ecosystem", "investor"].includes(key) ? "research" : key}/>{labels[key]}{key === "hypotheses" && passport && <span className="nav-count">{passport.hypotheses.length}</span>}</button>)}</nav>
      <div className="side-note"><span className="eyebrow">YOUR NEXT CHAPTER</span><p>Good ventures begin<br/>with better questions.</p><span className="side-line"/></div>
      <a className="company-link" href="/company-os" aria-label="Company OS roadmap"><Icon name="company"/><span>Company OS<small>Separate operating workspace</small></span><Icon name="arrow" size={16}/></a>
      <button className="account-settings-link" type="button" onClick={() => setShowAccount(true)} aria-label="Account settings">Account settings</button>
      <div className="profile"><div className="avatar">F</div><div><strong>{founder.name}</strong><small>Personal workspace</small></div><button className="icon-button" aria-label="Sign out" onClick={() => void signOut()}><Icon name="exit"/></button></div>
    </aside>
    <div className="work-area">
      <header className="topbar"><div><span>Workspace</span><b>/</b><strong>{labels[view]}</strong></div><button className="text-button" onClick={async () => { try { if (passport) setPassport(await api<Passport>(`/ventures/${passport.venture.id}/passport`)); } catch(e) { setError(e instanceof Error ? e.message : "Refresh failed."); } }}>Refresh Passport</button><span className="foundation-tag"><span/> Evidence workspace</span></header>
      <main id="main" className="main-content">
        <ErrorNotice message={error}/>
        <ErrorNotice message={authNotice?.error || ""}/>
        {authNotice?.connected && <div className="saved-notice"><span>{authNotice.connected} is connected to your founder workspace.</span><button className="text-button" onClick={() => setAuthNotice(null)}>Dismiss</button></div>}
        {!passport ? <Onboarding onSaved={value => { setPassport(value); setView("home"); }}/>
        : <>
          <div className="page-heading"><div><p className="eyebrow">{view === "home" ? "A LITTLE CLARITY. A REAL NEXT STEP." : "YOUR VENTURE, WITH CONTEXT."}</p><h1>{view === "home" ? "Make your next move count." : labels[view]}</h1><p>{view === "home" ? "Turn what you believe into something you can test." : "Keep your assumptions visible and your progress grounded."}</p></div>{view === "passport" ? <button className="button secondary" onClick={exportPassport}><Icon name="download" size={17}/>Export JSON</button> : <button className="button primary" onClick={() => setShowAdd(true)}><Icon name="plus" size={17}/>Add hypothesis</button>}</div>
          {view === "home" && <>
            <section className="venture-hero"><div className="hero-copy"><span className="pill light">YOUR VENTURE · IDEA STAGE</span><h2>{passport.venture.name}</h2><p>{passport.venture.idea}</p><div className="hero-meta"><span>{passport.venture.geography}</span><i/>Passport revision {passport.venture.revision}</div><button className="text-button" onClick={() => setView("passport")}>Open Venture Passport <Icon name="arrow" size={18}/></button></div><div className="forge-orbit" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><div className="orbit-core"><Mark/></div><span className="orbit-point p1"/><span className="orbit-point p2"/><span className="orbit-label">BUILD WITH INTENTION</span></div></section>
            <div className="stats"><Metric label="Open hypotheses" value={passport.hypotheses.length} note="Ready to investigate"/><Metric label="Evidence recorded" value={passport.evidence_count} note="Sources with provenance"/><Metric label="Founder decisions" value={passport.decision_count} note="With a recorded rationale"/></div>
            <section className="concept-strip"><div><span className="eyebrow">USER · FOUNDER STATED</span><p>{passport.venture.customer_segment}</p></div><div><span className="eyebrow">BUYER · {buyer === "unknown" ? "UNKNOWN UNTIL STATED" : "FOUNDER STATED"}</span><p>{buyer === "unknown" ? "Define your buyer in Model Studio" : buyer}</p></div><div><span className="eyebrow">REVIEWED CYCLES</span><p>{records(passport).completed_cycles} evidence-to-decision cycles</p></div></section><ToolPanel tool="home" passport={passport} onSaved={setPassport}/><div className="two-columns"><section className="card next-step"><div className="section-top"><span className="eyebrow">FOCUS FOR TODAY</span><span className="step-number">01</span></div><h2>Name the assumption<br/>that matters most.</h2><p>What must be true for this venture to work? Capture one clear, testable statement before gathering evidence.</p><button className="button primary" onClick={() => setShowAdd(true)}>Capture a hypothesis <Icon name="arrow" size={17}/></button></section><section className="card"><div className="section-top"><h2>What you believe</h2><button className="text-button" onClick={() => setView("hypotheses")}>View all <Icon name="arrow" size={16}/></button></div><div className="compact-hypotheses">{passport.hypotheses.slice(0, 3).map((item, index) => <div key={item.id}><span className="hyp-number">H{String(index + 1).padStart(2, "0")}</span><div><p>{item.statement}</p><span className="status">Unvalidated</span></div></div>)}</div></section></div>
            <section className="engine-section"><div className="section-top"><div><span className="eyebrow">THE PATH AHEAD</span><h2>Three engines. One learning loop.</h2></div><span className="subtle">Choose your next mission</span></div><div className="engine-grid">{[{key:"research", icon:"research", name:"Research Desk", description:"Find the sources that support — or challenge — your thinking."},{key:"customer",icon:"customer",name:"Customer Lab",description:"Bring real customer observations into the conversation."},{key:"experiment",icon:"experiment",name:"Experiment Lab",description:"Turn a critical unknown into a measurable test."}].map(engine => <article key={engine.name}><span className="engine-icon"><Icon name={engine.icon} size={23}/></span><button className="planned-tag tool-open" onClick={() => setView(engine.key as Tool)}>Open</button><h3>{engine.name}</h3><p>{engine.description}</p></article>)}</div></section>
          </>}
          {view === "passport" && <><section className="card passport-card"><div className="section-top"><span className="eyebrow">VENTURE PASSPORT</span><span className="pill">Revision {passport.venture.revision}</span></div><h2>{passport.venture.name}</h2><p className="passport-idea">{passport.venture.idea}</p><dl className="passport-facts"><div><dt>Customer segment</dt><dd>{passport.venture.customer_segment}</dd></div><div><dt>Geography</dt><dd>{passport.venture.geography}</dd></div><div><dt>Current focus</dt><dd>Idea</dd></div><div><dt>Started</dt><dd>{date(passport.venture.created_at)}</dd></div></dl></section><Hypotheses passport={passport}/><section className="evidence-note"><Icon name="research"/><div><h3>A clear starting point.</h3><p>Your statements are stored as founder assumptions. Review the sources, locked protocols and decisions below. Acceptance never changes a source into proven truth.</p></div></section><ToolPanel tool="passport" passport={passport} onSaved={setPassport}/></>}
          {view === "hypotheses" && <Hypotheses passport={passport}/>}
          {view === "pipelines" && <Pipelines passport={passport} onSaved={setPassport}/>}
          {view === "activity" && <section className="card"><h2>Your venture timeline</h2><div className="timeline">{passport.activity.map(item => <div key={item.id}><span className="timeline-dot"/><div><strong>{item.description}</strong><p>{date(item.created_at)}</p></div><span className="pill">Founder</span></div>)}</div></section>}
          {!["home", "passport", "hypotheses", "activity", "pipelines"].includes(view) && <ToolPanel key={view} tool={view as Tool} passport={passport} onSaved={setPassport}/>}
          <footer className="workspace-footer"><span><span className="tiny-dot"/> Your thinking, kept in context.</span><span>Venture Forge · Product Engine</span></footer>
        </>}
      </main>
    </div>
    {showAdd && passport && <AddHypothesis passport={passport} onClose={() => setShowAdd(false)} onSaved={value => { setPassport(value); setShowAdd(false); }} onRefresh={() => void restore()}/>}
    {showAccount && <AccountConnections onClose={() => setShowAccount(false)}/>}
  </div>;
}

function Metric({label, value, note}: {label: string; value: number; note: string}) { return <div className="metric"><span>{label}</span><strong>{String(value).padStart(2,"0")}</strong><small>{note}</small></div>; }

function Hypotheses({passport}: {passport: Passport}) { return <section className="card hypothesis-section"><div className="section-top"><h2>Hypothesis registry</h2><span className="subtle">{passport.hypotheses.length} open</span></div><p className="section-description">A belief becomes evidence only after you investigate it.</p><div className="hypothesis-list">{passport.hypotheses.map((item, index) => <article key={item.id}><span className="hyp-number">H{String(index+1).padStart(2,"0")}</span><div><span className="eyebrow">{item.category}</span><h3>{item.statement}</h3><p>Founder assertion · {date(item.created_at)}</p></div><span className="status">Unvalidated</span></article>)}</div></section>; }

function Onboarding({onSaved}: {onSaved: (value:Passport) => void}) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const requestKey = useRef(crypto.randomUUID());
  async function submit(event:FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); setError(""); const form = new FormData(event.currentTarget); const body = Object.fromEntries(form.entries()) as unknown as VentureCreate; try { const result = await api<Passport>("/ventures", {method:"POST",headers:{"Idempotency-Key":requestKey.current},body:JSON.stringify(body)}); onSaved(result); } catch(e) { setError(e instanceof Error ? e.message : "Couldn't create the venture."); } finally { setBusy(false); } }
  return <><div className="page-heading"><div><p className="eyebrow">YOUR FIRST STEP</p><h1>Give your idea a place to grow.</h1><p>Start with what you know. Make room for what you’ll learn.</p></div><span className="pill">01 / Foundation</span></div><div className="onboarding-grid"><section className="card"><h2>Create your Venture Passport</h2><p className="section-description">A living record of your venture, starting with one honest assumption.</p><form className="venture-form" onSubmit={submit} onChange={() => { requestKey.current = crypto.randomUUID(); }}><label>Venture name<input name="name" required minLength={2} maxLength={120} placeholder="What are you building?"/></label><label>The idea<textarea name="idea" required minLength={10} maxLength={2000} rows={3} placeholder="Describe the problem you want to solve and your approach."/></label><div className="form-row"><label>Who is it for?<input name="customer_segment" required minLength={3} maxLength={300} placeholder="Your first customer segment"/></label><label>Where will you begin?<input name="geography" required minLength={2} maxLength={120} placeholder="City, region or market"/></label></div><label>Your first hypothesis<textarea name="first_hypothesis" required minLength={10} maxLength={1500} rows={3} placeholder="I believe this customer has this problem because…"/><small>Saved as an unvalidated founder assumption.</small></label><ErrorNotice message={error}/><button className="button primary" disabled={busy}>{busy ? "Creating your Passport…" : "Create Venture Passport"}<Icon name="arrow" size={18}/></button></form></section><aside className="onboarding-aside"><span className="engine-icon"><Icon name="hypotheses" size={28}/></span><h2>Clarity starts<br/>with an assumption.</h2><p>You don’t need all the answers. A good hypothesis gives you something specific to investigate.</p><div className="principle"><span>01</span><div><h3>Say what you believe</h3><p>Be specific about the customer and problem.</p></div></div><div className="principle"><span>02</span><div><h3>Keep evidence separate</h3><p>A founder’s conviction is a starting point for learning.</p></div></div><div className="principle"><span>03</span><div><h3>Decide with context</h3><p>Your Passport will keep the reasoning behind your next move.</p></div></div></aside></div></>;
}

function AddHypothesis({passport,onClose,onSaved,onRefresh}: {passport:Passport;onClose:()=>void;onSaved:(value:Passport)=>void;onRefresh:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null); const [busy,setBusy]=useState(false); const [error,setError]=useState(""); const [conflict,setConflict]=useState(false); const key=useRef(crypto.randomUUID());
  useEffect(()=>{const current=dialog.current; current?.showModal(); return ()=>current?.close();},[]);
  async function submit(event:FormEvent<HTMLFormElement>) {event.preventDefault();setBusy(true);setError("");const data=new FormData(event.currentTarget);const body:HypothesisCreate={statement:String(data.get("statement")),category:data.get("category") as HypothesisCreate["category"],expected_revision:passport.venture.revision};try{onSaved(await api<Passport>(`/ventures/${passport.venture.id}/hypotheses`,{method:"POST",headers:{"Idempotency-Key":key.current},body:JSON.stringify(body)}));}catch(e){setError(e instanceof Error?e.message:"Couldn't save hypothesis.");setConflict(e instanceof ApiError&&e.status===409);}finally{setBusy(false);}}
  return <dialog ref={dialog} onCancel={onClose} aria-labelledby="hypothesis-title"><div className="section-top"><span className="eyebrow">MAKE IT TESTABLE</span><button className="icon-button" aria-label="Close hypothesis form" onClick={onClose}><Icon name="close"/></button></div><h2 id="hypothesis-title">What do you believe?</h2><p className="section-description">Capture a statement you can investigate with real evidence.</p><form onSubmit={submit} onChange={()=>{key.current=crypto.randomUUID();}}><label>Hypothesis<textarea name="statement" autoFocus required minLength={10} maxLength={1500} rows={4} placeholder="I believe…"/></label><label>Category<select name="category"><option value="problem">Problem</option><option value="customer">Customer</option><option value="pricing">Pricing</option><option value="solution">Solution</option></select></label><div className="form-note"><span className="status">Unvalidated</span><p>Recorded as a founder assertion. Link receipts in Research Desk or Customer Lab.</p></div><ErrorNotice message={error}/>{conflict&&<button type="button" className="button secondary" onClick={()=>{onClose();onRefresh();}}>Reload Passport</button>}<div className="dialog-actions"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button primary" disabled={busy||conflict}>{busy?"Saving…":"Save hypothesis"}<Icon name="plus" size={17}/></button></div></form></dialog>;
}
