"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, type Passport } from "@/lib/api";
import { AgentConsole } from "./agents";
import { ResearchSources, ControlledExport } from "./mvp-panels";
import { WorkspaceResult, type WorkspaceReport } from "./schema-fields";

export const toolNames = {
  home: "Mentor Home", research: "Research Desk", market: "Market Lab", customer: "Customer Lab",
  competitor: "Competitor Room", model: "Model Studio", finance: "Finance Lab", experiment: "MVP and Experiment Lab",
  simulation: "Simulation Arena", academy: "Founder Academy", ecosystem: "Ecosystem Hub", investor: "Investor Room", passport: "Venture Passport",
};
export type Tool = keyof typeof toolNames;
type Evidence = { id: string; hypothesis_id: string; title: string; kind: string; content: string; locator: string; relation: string; limitations: string; consent: string; collected_on: string; withdrawn: boolean; participant_code: string | null; content_hash: string };
type Artifact = { id: string; capability: string; title: string; status: string; result: Record<string, unknown>; created_at: string; formula_version: string };
type Experiment = { id: string; hypothesis_id: string; title: string; protocol: { metric: string; threshold_percent: string; minimum_n: number; end_date: string; intervention: string; stop_rule: string }; protocol_hash: string; result: { n: number; recorded_n: number; successes: number; rate_percent: string | null; outcome: string; threshold_percent: string }; observations: unknown[] };
type Decision = { id: string; target_id: string; target_type: string; choice: string; rationale: string; stale: boolean; result_snapshot: Record<string, unknown> };
type Run = { id: string; status: string; objective: string; proposal: Record<string, unknown> };
export type Records = { evidence: Evidence[]; artifacts: Artifact[]; experiments: Experiment[]; decisions: Decision[]; runs: Run[]; completed_cycles: number };
export function records(passport: Passport): Records { return passport as unknown as Records; }

type Props = { tool: Tool; passport: Passport; onSaved: (p: Passport) => void };
type Field = { key: string; label: string; type?: "number" | "date" | "textarea"; hint?: string; options?: string[]; required?: boolean; min?: number; max?: number; step?: string; initial?: string };
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const tomorrow = () => { const d = new Date(); d.setDate(d.getDate() + 7); return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(d); };

function EntryForm({ title, description, fields, action, onSubmit, children }: { title: string; description?: string; fields: Field[]; action: string; onSubmit: (values: Record<string, string>) => Promise<void>; children?: ReactNode }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget;
    try { await onSubmit(Object.fromEntries(new FormData(form)) as Record<string, string>); form.reset(); }
    catch (e) { setError(e instanceof Error ? e.message : "Couldn't save. Please try again."); }
    finally { setBusy(false); }
  }
  return <section className="card tool-form"><h2>{title}</h2>{description && <p className="section-description">{description}</p>}<form onSubmit={submit}>{children}<div className="tool-fields">{fields.map(f => <label key={f.key} className={f.type === "textarea" ? "wide-field" : ""}>{f.label}{f.options ? <select name={f.key} defaultValue={f.initial}>{f.options.map(o => <option key={o} value={o}>{o.replaceAll("_", " ")}</option>)}</select> : f.type === "textarea" ? <textarea name={f.key} rows={3} required={f.required !== false} minLength={f.min ?? 3} maxLength={f.max ?? 4000} placeholder={f.hint}/> : <input name={f.key} type={f.type || "text"} defaultValue={f.initial} placeholder={f.hint} required={f.required !== false} min={f.min ?? (f.type === "number" ? 0 : undefined)} max={f.max} step={f.step || (f.type === "number" ? "0.01" : undefined)} maxLength={f.type ? undefined : 300}/>}</label>)}</div>{error && <p className="error" role="alert">{error}</p>}<button className="button primary" disabled={busy}>{busy ? "Saving..." : action} <span aria-hidden="true">↗</span></button></form></section>;
}

function HypothesisPicker({ passport }: { passport: Passport }) { return <label>Linked hypothesis<select name="hypothesis_id">{passport.hypotheses.map((h, i) => <option key={h.id} value={h.id}>H{String(i + 1).padStart(2, "0")} · {h.statement.slice(0, 100)}</option>)}</select></label>; }
function Empty({ children }: { children: ReactNode }) { return <div className="empty-state"><span className="empty-symbol" aria-hidden="true">◇</span><p>{children}</p></div>; }
function Result({ result }: { result: Record<string, unknown> }) { return <dl className="result-grid">{Object.entries(result).filter(([k]) => !["fields", "receipts", "formula", "formula_version", "unknowns", "suggested_missions", "limitations"].includes(k)).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value === null ? "Not defined" : Array.isArray(value) && value.every(v => typeof v === "string") ? <ul className="unknown-list">{value.map((v, i) => <li key={i}>{v}</li>)}</ul> : typeof value === "object" ? JSON.stringify(value) : String(value).replaceAll("_", " ")}</dd></div>)}</dl>; }

const worksheetFields: Record<string, string[]> = {
  model: ["Buyer", "User", "Value proposition", "Customer relationships", "Channels", "Key activities", "Key resources", "Key partners", "Cost structure", "Revenue streams", "Pricing hypothesis", "Next pricing test"],
  competitor: ["Customer job", "Alternative / status quo", "Official source / capture date", "Observed features", "Price (unknown if unavailable)", "Switching barriers", "Differentiation hypothesis", "Next switching test"],
  academy: ["Current mission", "Skill to practise", "Applied exercise", "Your independent answer", "Assistance received", "Rubric / reviewer notes", "Delayed transfer test date"],
  ecosystem: ["Programme name", "Official programme URL", "Last checked date", "Stage / sector / geography", "Eligibility known", "Eligibility unknown", "Call expiry date", "Next verification step"],
  investor: ["Financing purpose", "Accepted financial model version", "Buyer / contract evidence", "Ownership and IP gaps", "Negative findings", "Milestones and use of funds", "Disclosure recipient (planning only)", "Next diligence step"],
};

const financeFields: Field[] = [
  ...[["price", "Price per unit (INR)"], ["volume", "Units sold"], ["direct_cost", "Total direct delivery cost (INR)"], ["fixed_cost", "Fixed cost (INR)"], ["collected_cash", "Cash actually collected (INR)"], ["cash_balance", "Starting cash balance (INR)"]].map(([key, label]) => ({ key, label, type: "number" as const, step: key === "volume" ? "1" : "0.01" })),
  { key: "period", label: "Period", options: ["month", "year", "cohort"] },
  { key: "acquisition_spend", label: "Acquisition spend (INR, optional)", type: "number", required: false, hint: "Sales and marketing costs already included above" },
  { key: "new_customers", label: "New paying customers (optional)", type: "number", required: false, step: "1", hint: "Same period as acquisition spend" },
  { key: "average_revenue_per_customer", label: "Average customer revenue per period (INR, optional)", type: "number", required: false, hint: "Per selected month or year" },
  { key: "customer_lifetime_periods", label: "Customer lifetime periods (optional)", type: "number", required: false, min: 0.01, hint: "Assumed number of the selected months or years" },
];

export function ToolPanel({ tool, passport, onSaved }: Props) {
  const data = records(passport), base = `/ventures/${passport.venture.id}`;
  const [notice, setNotice] = useState("");
  const [specialistOpen, setSpecialistOpen] = useState(false);
  const keys = useRef(new Map<string, string>());
  async function command(path: string, values: Record<string, unknown>, run = false) {
    const body = JSON.stringify({ ...values, expected_revision: passport.venture.revision });
    const signature = path + body;
    let key = keys.current.get(signature);
    if (!key) { key = crypto.randomUUID(); keys.current.set(signature, key); }
    const result = await api<Passport>(base + path, { method: "POST", body, headers: { "Idempotency-Key": key } });
    if (run) onSaved(await api<Passport>(base + "/passport")); else onSaved(result);
    setNotice("Saved to your Venture Passport.");
  }
  async function refresh() { try { onSaved(await api<Passport>(base + "/passport")); } catch (e) { setNotice(e instanceof Error ? e.message : "Refresh failed."); } }
  useEffect(() => {
    if (!data.runs.some(r => r.status === "QUEUED" || r.status === "RUNNING")) return;
    const timer = setInterval(() => { void refresh(); }, 2000);
    return () => clearInterval(timer);
  }, [passport]); // Poll only while a durable run is pending.

  const reviewed = (id: string) => data.decisions.some(d => d.target_id === id);
  const review = (target_type: string, target_id: string) => <EntryForm title="Your decision" fields={[{ key: "choice", label: "Decision", options: target_type === "experiment" ? ["continue", "revise", "stop"] : ["accept", "reject"] }, { key: "rationale", label: "Rationale and next commitment", type: "textarea", min: 10 }]} action="Record founder decision" onSubmit={v => command("/decisions", { ...v, target_type, target_id })}/>;
  const eligibleEvidence = data.evidence.filter(e => !e.withdrawn);
  const receiptFields: Field[] = [
    { key: "title", label: "Receipt title", hint: "A specific source or observation" },
    { key: "locator", label: "Source URL, page or note locator", hint: "URL + page, or interview note + timestamp" },
    { key: "content", label: tool === "customer" ? "Observed behaviour or exact notes" : "Original source excerpt", type: "textarea", min: 10, max: 20000 },
    { key: "collected_on", label: "Collected on", type: "date", initial: today() },
    { key: "relation", label: "Relationship to the hypothesis", options: ["contextualizes", "supports", "contradicts"] },
    { key: "limitations", label: "Scope and limitations", type: "textarea", hint: "Who, where, when; what this source cannot establish" },
    ...(tool === "customer" ? [{ key: "participant_code", label: "Participant code", hint: "P01 · use a code, not a person's name" }, { key: "consent", label: "Participant consent", options: ["notes_only", "quote_permitted"] }] : [{ key: "consent", label: "Source permission", options: ["public_source", "private_observation"] }]),
  ];
  const artifacts = data.artifacts.filter(a => a.capability === tool);

  return <div className="tools-area">{notice && <div className="saved-notice" role="status">{notice}<button className="text-button" onClick={() => setNotice("")} aria-label="Dismiss notification">×</button></div>}
    <details className="card" onToggle={e => setSpecialistOpen(e.currentTarget.open)}><summary>Run the {toolNames[tool]} specialist</summary>{specialistOpen && <AgentConsole key={tool} agent={tool} passport={passport} onSaved={onSaved}/>}</details>
    {tool === "research" && <ResearchSources passport={passport} onSaved={onSaved}/>}
    {["passport", "research", "market", "customer", "competitor", "model", "finance", "investor"].includes(tool) && <details className="card"><summary>Export selected accepted versions</summary><ControlledExport passport={passport}/></details>}
    {tool === "home" && <details className="card concept-edit"><summary>Edit your Concept Map</summary><EntryForm title="Your purpose, in your words" description="Corrections preserve the previous version and make dependent worksheets stale." fields={[{ key: "name", label: "Venture name", initial: passport.venture.name }, { key: "idea", label: "The idea and purpose", initial: passport.venture.idea }, { key: "customer_segment", label: "User or customer segment", initial: passport.venture.customer_segment }, { key: "geography", label: "Geography", initial: passport.venture.geography }]} action="Save concept correction" onSubmit={v => command("/intake", v)}/></details>}
    {(tool === "research" || tool === "customer") && <>
      <div className="tool-split"><EntryForm title={tool === "customer" ? "Capture a customer observation" : "Add an evidence receipt"} description={tool === "customer" ? "Keep observation separate from interpretation. Record consent and preserve contrary cases." : "Paste the original excerpt and its location. Capture establishes provenance; it does not establish truth."} fields={receiptFields} action="Save evidence receipt" onSubmit={v => command("/evidence", { ...v, kind: tool === "customer" ? "interview" : "source" })}><HypothesisPicker passport={passport}/></EntryForm>
      <section className="card quiet-card"><span className="eyebrow">EVIDENCE, WITH CONTEXT</span><h2>A receipt for every claim.</h2><p>Direct observations, source quotations and assumptions stay distinct. Contrary findings belong in the record.</p><div className="rule-row"><span>01</span><p>Locate the original source.</p></div><div className="rule-row"><span>02</span><p>Describe scope and limitations.</p></div><div className="rule-row"><span>03</span><p>Review before making a decision.</p></div><strong>{eligibleEvidence.length} active receipts</strong></section></div>
      <section className="card"><div className="section-top"><h2>Source ledger</h2><span className="pill">{data.evidence.length} captured</span></div>{!data.evidence.length ? <Empty>Your first source belongs here. Add a receipt to begin.</Empty> : <div className="receipt-list">{data.evidence.map(e => <article key={e.id} className={e.withdrawn ? "withdrawn" : ""}><div className="section-top"><h3>{e.title}</h3><span className="status">{e.withdrawn ? "Withdrawn" : e.relation}</span></div><blockquote>{e.content}</blockquote><p className="source-location">{e.locator} · {e.collected_on} · {e.consent.replaceAll("_", " ")}</p><p><strong>Limitations:</strong> {e.limitations}</p><details><summary>Source fingerprint</summary><code>{e.content_hash}</code></details>{!e.withdrawn && <button className="text-button danger" onClick={() => { void command(`/evidence/${e.id}/withdraw`, {}).catch(e => setNotice(e.message)); }}>Withdraw source and invalidate dependencies</button>}</article>)}</div>}</section>
      <EntryForm title="Choose a bounded evidence mission" description="Review permitted receipts with rules. The result is a proposal; no live search or model generation is performed." fields={[{ key: "objective", label: "Your decision question", type: "textarea", min: 10 }]} action="Start evidence review" onSubmit={v => command("/runs", { ...v, capability: tool, evidence_ids: eligibleEvidence.filter(e => e.hypothesis_id === v.hypothesis_id).map(e => e.id) }, true)}><HypothesisPicker passport={passport}/></EntryForm>
      {data.runs.map(r => <section className="card" key={r.id}><div className="section-top"><h2>{r.objective}</h2><span className="status">{r.status.replaceAll("_", " ")}</span></div>{r.status === "QUEUED" && <p className="section-description">Waiting for the local worker. The launcher starts it automatically.</p>}<Result result={r.proposal}/>{Array.isArray(r.proposal.unknowns) && <ul className="unknown-list">{r.proposal.unknowns.map((s, i) => <li key={i}>{String(s)}</li>)}</ul>}{r.status === "AWAITING_REVIEW" && !reviewed(r.id) && review("run", r.id)}</section>)}
    </>}
    {["market", "finance", "simulation"].includes(tool) && <EntryForm title={tool === "market" ? "Size a buying-unit scenario" : tool === "simulation" ? "Explore an explicit scenario" : "Calculate unit economics"} description={tool === "market" ? "Use one buying unit. Inputs remain assumptions until backed by evidence." : "All amounts use INR and the same period. Revenue and collected cash are separate. CAC and LTV inputs are optional; LTV needs month or year units. Acquisition spend classifies costs already included above."} fields={tool === "market" ? [
      { key: "title", label: "Scenario name" }, { key: "unit", label: "Buying unit", hint: "Institutions, accounts or customers" },
      ...[["total_accounts", "Total accounts (TAM)"], ["serviceable_accounts", "Serviceable accounts (SAM)"], ["reachable_accounts", "Reachable accounts"], ["capacity", "Delivery capacity"], ["price", "Price per unit (INR)"]].map(([key, label]) => ({ key, label, type: "number" as const, step: key === "price" ? "0.01" : "1" })),
      { key: "period", label: "Period", options: ["year", "month", "cohort"] },
    ] : [{ key: "title", label: "Scenario name" }, ...financeFields]} action={tool === "simulation" ? "Run simulated scenario" : "Calculate and save proposal"} onSubmit={v => { const { title, ...rawInputs } = v; const inputs: Record<string, unknown> = Object.fromEntries(Object.entries(rawInputs).filter(([, value]) => value.trim() !== "")); for (const k of ["volume", "new_customers", "total_accounts", "serviceable_accounts", "reachable_accounts", "capacity"]) if (k in inputs) inputs[k] = Number(inputs[k]); return command("/artifacts", { capability: tool, title, inputs }); }}/>}
    {worksheetFields[tool] && <EntryForm title={tool === "model" ? "Build your business model" : `Create a ${toolNames[tool].toLowerCase()} worksheet`} description={tool === "model" ? "Keep buyer and price unknown until the founder states them. A complete canvas is still a set of assumptions." : tool === "ecosystem" ? "Record your own programme research. Recheck the official call before treating an opportunity as open." : "Create a versioned worksheet with your own inputs. Acceptance preserves your decision; it does not verify every statement."} fields={[{ key: "title", label: "Worksheet name" }, ...worksheetFields[tool].map((label, i) => ({ key: `f${i}`, label, type: "textarea" as const, required: false, hint: "Unknown until stated or supported" }))]} action="Save worksheet proposal" onSubmit={v => { const fields = Object.fromEntries(worksheetFields[tool].map((label, i) => [label, v[`f${i}`]?.trim() || "unknown"])); return command("/artifacts", { capability: tool, title: v.title, inputs: { fields }, evidence_ids: eligibleEvidence.map(e => e.id) }); }}/>}
    {artifacts.map(a => { const workspace = (a.result.data as Record<string, unknown> | undefined)?.workspace as WorkspaceReport | undefined; return <section className="card artifact-card" key={a.id}><div className="section-top"><h2>{a.title}</h2><span className={`status ${a.status === "STALE" ? "danger" : ""}`}>{a.status}</span></div><p className="source-location">{a.formula_version} · {new Date(a.created_at).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata" })}</p>{workspace ? <WorkspaceResult report={workspace}/> : a.result.fields ? <Result result={a.result.fields as Record<string, unknown>}/> : <Result result={a.result}/>} {typeof a.result.formula === "string" && <p className="formula-note">{a.result.formula}</p>}{!reviewed(a.id) && a.status === "PROPOSED" && review("artifact", a.id)}</section>; })}
    {tool === "experiment" && <>
      <EntryForm title="Predeclare and lock a real-world test" description="Choose the threshold before collecting results. A locked protocol cannot be edited; a changed test needs a new protocol." fields={[{ key: "title", label: "Experiment name" }, { key: "intervention", label: "Intervention and recruitment plan", type: "textarea", min: 10 }, { key: "metric", label: "Binary success metric", hint: "A dated pilot commitment" }, { key: "threshold_percent", label: "Success threshold (%)", type: "number", max: 100 }, { key: "minimum_n", label: "Minimum sample size", type: "number", min: 1, step: "1" }, { key: "end_date", label: "Planned end date", type: "date", initial: tomorrow() }, { key: "stop_rule", label: "Stop rule", type: "textarea" }]} action="Approve and lock protocol" onSubmit={v => { const { title, hypothesis_id, ...protocol } = v; return command("/experiments", { title, hypothesis_id, protocol: { ...protocol, minimum_n: Number(protocol.minimum_n) } }); }}><HypothesisPicker passport={passport}/></EntryForm>
      {!data.experiments.length && <Empty>Lock your first test, then collect real observations in Customer Lab.</Empty>}
      {data.experiments.map(e => <section className="card experiment-card" key={e.id}><div className="section-top"><h2>{e.title}</h2><span className="pill">Protocol locked</span></div><p className="section-description">{e.protocol.intervention}</p><dl className="result-grid"><div><dt>Metric</dt><dd>{e.protocol.metric}</dd></div><div><dt>Predeclared threshold</dt><dd>{e.protocol.threshold_percent}% · minimum {e.protocol.minimum_n}</dd></div><div><dt>End date</dt><dd>{e.protocol.end_date}</dd></div><div><dt>Stop rule</dt><dd>{e.protocol.stop_rule}</dd></div></dl><div className="experiment-outcome"><strong>{e.result.rate_percent ?? "—"}{e.result.rate_percent !== null && "%"}</strong><div><span>{e.result.successes} successes / {e.result.n} valid observations</span><p>{e.result.outcome.replaceAll("_", " ")}</p></div></div><details><summary>Protocol fingerprint</summary><code>{e.protocol_hash}</code></details>{!reviewed(e.id) && <>
        {eligibleEvidence.filter(r => r.hypothesis_id === e.hypothesis_id && r.kind !== "source").length ? <EntryForm title="Append an observed result" fields={[{ key: "participant_code", label: "Participant code" }, { key: "success", label: "Metric achieved?", options: ["false", "true"] }, { key: "instrument_valid", label: "Instrumentation valid?", options: ["true", "false"] }, { key: "deviation", label: "Protocol deviations", type: "textarea", required: false }]} action="Record observation" onSubmit={v => command(`/experiments/${e.id}/observations`, { ...v, success: v.success === "true", instrument_valid: v.instrument_valid === "true" })}><label>Observation receipt<select name="receipt_id">{eligibleEvidence.filter(r => r.hypothesis_id === e.hypothesis_id && r.kind !== "source").map(r => <option key={r.id} value={r.id}>{r.title} · {r.participant_code || "observation"}</option>)}</select></label></EntryForm> : <p className="formula-note">Capture a consented interview in Customer Lab to add an observed result.</p>}
        {review("experiment", e.id)}
      </>}</section>)}
    </>}
    {tool === "passport" && <><div className="stats"><div className="metric"><span>Active receipts</span><strong>{passport.evidence_count}</strong><small>With provenance and limitations</small></div><div className="metric"><span>Founder decisions</span><strong>{data.decisions.length}</strong><small>Includes inconclusive outcomes</small></div><div className="metric"><span>Reviewed cycles</span><strong>{data.completed_cycles}</strong><small>Real observations, adequate sample</small></div></div><section className="card"><h2>Decision history</h2>{!data.decisions.length ? <Empty>Review a proposal or an experiment to record your next commitment.</Empty> : data.decisions.map(d => <article className="decision-row" key={d.id}><span className="status">{d.stale ? "STALE" : d.choice}</span><div><h3>{d.target_type} decision</h3><p>{d.rationale}</p><Result result={d.result_snapshot}/></div></article>)}</section><section className="card"><h2>Evidence trail</h2><p className="section-description">{data.evidence.length} receipts → {data.experiments.length} locked experiments → {data.decisions.length} founder decisions. Withdrawn records invalidate dependent views.</p><div className="timeline">{passport.activity.map(a => <div key={a.id}><span className="timeline-dot"/><div><strong>{a.description}</strong><p>{new Date(a.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}</p></div></div>)}</div></section></>}
  </div>;
}
