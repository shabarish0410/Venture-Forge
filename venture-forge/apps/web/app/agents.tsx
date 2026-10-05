"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, type Passport } from "@/lib/api";
import { records, type Tool } from "./tools";

type Schema = { type?: string; title?: string; description?: string; default?: unknown; enum?: string[]; anyOf?: Schema[]; items?: Schema; minimum?: number; maximum?: number; minLength?: number; maxLength?: number; format?: string; $ref?: string; properties?: Record<string, Schema>; required?: string[]; $defs?: Record<string, Schema> };
type ModelRequirements = { task: string; reasoning: string; min_context_tokens: number; max_output_tokens: number; structured_outputs: boolean; tool_calling: boolean; deterministic_operations: string[] };
type ModelProfile = { name: string; provider: string; model_id: string; ready: boolean; location: string; reasoning: string; context_tokens: number; tool_calling: boolean; structured_outputs: boolean };
type Specialist = { id: Tool; name: string; workspace: string; description: string; receives: Tool[]; sends: Tool[]; tools: string[]; output_type: string; parameters_schema: Schema; model_requirements: ModelRequirements };
type Catalog = { agents: Specialist[]; templates: { id: string; name: string; stages: { agent_id: Tool; dependencies: Tool[] }[] }[]; model: { configured: boolean; policy: string; default_mode: string; profiles: ModelProfile[] } };
export type AgentRun = { id: string; agent_id: Tool; stage_id?: string; objective: string; status: string; artifact_id?: string; result_hash: string; error_code?: string; cost_inr: number; trace: unknown[]; context: unknown; result: { summary?: string; data?: Record<string, unknown>; unknowns?: string[]; limitations?: string[]; evidence_ids?: string[]; next_action?: string; evidence_class?: string; mode?: string } };
type Stage = { id: string; agent_id: Tool; dependencies: Tool[]; status: string; run_id?: string; artifact_id?: string };
type Pipeline = { id: string; template: string; name: string; hypothesis_id: string; objective: string; status: string; stages: Stage[] };
type Handoff = { id: string; from_run_id: string; to_agent_id: Tool; artifact_id: string; status: string };
export function agentRecords(p: Passport) { return p as unknown as { agent_runs: AgentRun[]; pipelines: Pipeline[]; handoffs: Handoff[] }; }

function useCatalog() {
  const [catalog, setCatalog] = useState<Catalog | null>(null), [error, setError] = useState("");
  useEffect(() => { let active = true; api<Catalog>("/agents").then(c => { if (active) setCatalog(c); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, []);
  return { catalog, error };
}
const label = (s: string) => s.replaceAll("_", " ");
function effective(field: Schema, root: Schema): Schema {
  if (field.$ref) return effective(root.$defs?.[field.$ref.split("/").at(-1)!] || {}, root);
  if (field.anyOf) return { ...effective(field.anyOf.find(s => s.type !== "null") || {}, root), ...field, anyOf: undefined };
  return field;
}
function parameterValue(field: Schema, root: Schema, value: string) {
  const resolved = effective(field, root);
  // Decimal schemas accept strings: preserve the typed amount for server arithmetic.
  const decimal = field.anyOf?.some(s => s.type === "number") && field.anyOf?.some(s => s.type === "string");
  return resolved.type === "integer" || (resolved.type === "number" && !decimal) ? Number(value) : value;
}
function Collection({ name, schema, root, sources }: { name: string; schema: Schema; root: Schema; sources: { id: string; title: string }[] }) {
  const [rows, setRows] = useState<string[]>([]); const item = effective(schema.items || {}, root);
  return <div className="wide-field agent-collection"><h3>{label(name)}</h3><p className="section-description">Enter your own records. Linked sources are included in this run.</p>{rows.map((id, index) => <fieldset key={id}><legend>{name === "alternatives" ? "Alternative" : "Opportunity"} {index + 1}</legend><div className="tool-fields">{Object.entries(item.properties || {}).map(([key, original]) => {
    const f = effective(original, root), fieldName = `parameter:${name}:${id}:${key}`, required = item.required?.includes(key);
    return <label key={key}>{label(key)}{key === "source_id" ? <select name={fieldName} required={required} aria-label={`${label(key)} ${index + 1}`}><option value="">Unknown / no source</option>{sources.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
      : f.enum ? <select name={fieldName} defaultValue={String(f.default || f.enum[0])} aria-label={`${label(key)} ${index + 1}`}>{f.enum.map(v => <option key={v}>{v}</option>)}</select>
      : <input name={fieldName} required={required} type={f.format === "date" ? "date" : key === "official_url" ? "url" : f.type === "number" || f.type === "integer" ? "number" : "text"} min={f.minimum} max={f.maximum} step="any" minLength={f.minLength} maxLength={f.maxLength} defaultValue={f.default == null ? "" : String(f.default)}/>}</label>;
  })}</div><button type="button" className="text-button danger" onClick={() => setRows(rows.filter(r => r !== id))}>Remove record {index + 1}</button></fieldset>)}<button type="button" className="button secondary" onClick={() => setRows([...rows, crypto.randomUUID()])}>Add {name === "alternatives" ? "alternative" : "opportunity"}</button></div>;
}
function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="subtle">Unknown</span>;
  if (Array.isArray(value)) return value.length ? <ul className="agent-values">{value.map((v, i) => <li key={i}><Value value={v}/></li>)}</ul> : <span className="subtle">None recorded</span>;
  if (typeof value === "object") return <dl className="agent-values">{Object.entries(value).map(([k, v]) => <div key={k}><dt>{label(k)}</dt><dd><Value value={v}/></dd></div>)}</dl>;
  return <span>{typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</span>;
}

function RoutingControls({ spec, catalog, mode, setMode }: { spec: Specialist; catalog: Catalog; mode: string; setMode: (value: string) => void }) {
  const [privacy, setPrivacy] = useState("cloud_allowed"), [profile, setProfile] = useState("");
  const requirements = spec.model_requirements;
  return <details open={catalog.model.configured}><summary>Hybrid routing, privacy and execution limits</summary>
    <p className="section-description">{requirements.reasoning} reasoning · at least {requirements.min_context_tokens.toLocaleString()} context tokens · validated structured output{requirements.tool_calling ? " · tool-call capability" : ""}. Complex tasks prefer a suitable cloud model. Calculations and workflow rules always run in code.</p>
    <div className="tool-fields"><label>Tool step cap<input name="steps" type="number" min={1} max={30} defaultValue={12}/></label><label>Time cap (seconds)<input name="seconds" type="number" min={1} max={120} defaultValue={60}/></label>
      <label>Execution mode<select aria-label="Execution mode" value={mode} onChange={e => setMode(e.target.value)}><option value="AUTO">Hybrid routing (recommended)</option><option value="RULE">Deterministic tools · ₹0</option><option value="MODEL" disabled={!catalog.model.configured}>Require a suitable model</option></select></label>
      {mode !== "RULE" && <><label>Processing policy<select aria-label="Processing policy" name="data_policy" value={privacy} onChange={e => { setPrivacy(e.target.value); setProfile(""); }}><option value="cloud_allowed">Cloud allowed · complex tasks prefer cloud</option><option value="local_only">Local only · privacy / offline</option></select></label>
        <label>Model profile<select aria-label="Model profile" name="preferred_profile" value={profile} onChange={e => setProfile(e.target.value)}><option value="">Choose automatically by capability and cost</option>{catalog.model.profiles.filter(p => privacy !== "local_only" || p.location === "local").map(p => <option key={p.name} value={p.name} disabled={!p.ready}>{p.name} · {p.provider} · {p.model_id}{!p.ready ? " · unavailable" : ""}</option>)}</select></label>
        <label>Maximum model cost (INR)<input name="cost" type="number" min={0} max={100} step="0.01" defaultValue={1}/></label>
        {catalog.model.configured && <label className="agent-check wide-field"><input name="model-consent" type="checkbox" required/><span>{privacy === "local_only" ? "Allow this run’s scoped context to be processed by configured local models only." : "Allow this run’s scoped context to be processed by the configured cloud or local provider selected by the router."}</span></label>}
      </>}
    </div>
    {!catalog.model.configured && <p className="section-description">No model profiles are ready. Hybrid mode uses deterministic tools until the server is configured. Research synthesis and model reasoning will remain unavailable.</p>}
    <p className="section-description">Source text is treated as data. Model analysis is labelled separately and cannot change calculations or send messages. Local-only requests never fall back to cloud.</p>
  </details>;
}

export function AgentConsole({ agent, passport, onSaved, stage, pipeline }: { agent: Tool; passport: Passport; onSaved: (p: Passport) => void; stage?: Stage; pipeline?: Pipeline }) {
  const { catalog, error: catalogError } = useCatalog();
  const [error, setError] = useState(""), [busy, setBusy] = useState(false), [mode, setMode] = useState("AUTO");
  const [hypothesis, setHypothesis] = useState(pipeline?.hypothesis_id || passport.hypotheses[0]?.id || "");
  const spec = catalog?.agents.find(a => a.id === agent);
  const data = records(passport), all = agentRecords(passport);
  const runs = all.agent_runs.filter(r => stage ? r.stage_id === stage.id : r.agent_id === agent && !r.stage_id);
  const base = `/ventures/${passport.venture.id}`;
  async function command(path: string, body: Record<string, unknown>) {
    await api(base + path, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ ...body, expected_revision: passport.venture.revision }) });
    onSaved(await api<Passport>(base + "/passport"));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!spec) return; setBusy(true); setError("");
    const f = new FormData(event.currentTarget);
    try {
      const parameters: Record<string, unknown> = {};
      for (const [key, field] of Object.entries(spec.parameters_schema.properties || {})) {
        const s = effective(field, spec.parameters_schema), v = String(f.get(`parameter:${key}`) ?? "");
        if (s.type === "array") {
          const items: Record<string, Record<string, unknown>> = {}; const itemSchema = effective(s.items || {}, spec.parameters_schema);
          for (const [name, value] of f.entries()) {
            if (!name.startsWith(`parameter:${key}:`) || !String(value).trim()) continue;
            const [, , row, property] = name.split(":"), prop = itemSchema.properties?.[property] || {};
            (items[row] ||= {})[property] = parameterValue(prop, spec.parameters_schema, String(value));
          }
          parameters[key] = Object.values(items);
        } else if (s.type === "boolean") parameters[key] = v === "on";
        else if (v.trim()) parameters[key] = s.type === "array" || s.type === "object" ? JSON.parse(v) : parameterValue(field, spec.parameters_schema, v);
      }
      const linked = Object.values(parameters).flatMap(value => Array.isArray(value) ? value.map(item => item.source_id).filter(Boolean) : []);
      await command("/agent-runs", { agent_id: agent, objective: f.get("objective"), hypothesis_id: hypothesis, stage_id: stage?.id, parameters, evidence_ids: [...new Set([...f.getAll("evidence"), ...linked])], artifact_ids: f.getAll("artifact"), experiment_ids: f.getAll("experiment"), mode, data_policy: f.get("data_policy") || "cloud_allowed", preferred_profile: f.get("preferred_profile") || null, allow_model_processing: f.get("model-consent") === "on", budget: { max_steps: Number(f.get("steps")), max_seconds: Number(f.get("seconds")), max_cost_inr: mode === "RULE" ? 0 : Number(f.get("cost")) } });
    } catch (e) { setError(e instanceof SyntaxError ? "Check the alternatives or opportunities JSON. Copy the example structure and enter your own records." : e instanceof Error ? e.message : "Run could not be queued."); }
    finally { setBusy(false); }
  }
  async function review(event: FormEvent<HTMLFormElement>, run: AgentRun) {
    event.preventDefault(); setBusy(true); setError(""); const f = new FormData(event.currentTarget);
    try { await command(`/agent-runs/${run.id}/review`, { choice: f.get("choice"), rationale: f.get("rationale"), expected_result_hash: run.result_hash }); }
    catch (e) { setError(e instanceof Error ? e.message : "Review failed."); } finally { setBusy(false); }
  }
  const canRun = !stage || ["READY", "NEEDS_INPUT", "FAILED", "CANCELLED", "STALE", "REJECTED"].includes(stage.status);
  return <section className="card specialist-console" aria-label={`${spec?.name || agent} specialist`}>
    <div className="section-top"><div><span className="eyebrow">SPECIALIST EXECUTION</span><h2>{spec?.name || "Loading specialist…"}</h2></div><span className="pill">{stage?.status.replaceAll("_", " ") || "Bounded mission"}</span></div>
    {(error || catalogError) && <p role="alert" className="error">{error || catalogError}</p>}
    {spec && catalog && <><p className="section-description">{spec.description} Accepted results become versioned Passport records and handoffs.</p>
      {canRun && <form onSubmit={submit} className="agent-form">
        <label>Specialist objective<textarea name="objective" required minLength={10} maxLength={2000} defaultValue={pipeline?.objective} placeholder="Which decision should this specialist help you make?" rows={2}/></label>
        <label>Linked hypothesis<select value={hypothesis} disabled={!!pipeline} onChange={e => setHypothesis(e.target.value)}>{passport.hypotheses.map(h => <option key={h.id} value={h.id}>{h.statement}</option>)}</select></label>
        <div className="tool-fields">{Object.entries(spec.parameters_schema.properties || {}).map(([key, original]) => {
          const field = effective(original, spec.parameters_schema), required = spec.parameters_schema.required?.includes(key), isArray = field.type === "array" || field.type === "object";
          if (isArray) return <Collection key={key} name={key} schema={field} root={spec.parameters_schema} sources={data.evidence.filter(e => !e.withdrawn && e.hypothesis_id === hypothesis)}/>;
          return <label key={key}>{label(key)}
            {field.enum ? <select name={`parameter:${key}`} defaultValue={String(field.default || field.enum[0])}>{field.enum.map(v => <option key={v}>{v}</option>)}</select>
              : field.type === "boolean" ? <input name={`parameter:${key}`} type="checkbox" defaultChecked={field.default === true}/>
              : <input name={`parameter:${key}`} required={required} type={field.format === "date" ? "date" : field.type === "integer" || field.type === "number" ? "number" : "text"} min={field.minimum} max={field.maximum} step={field.type === "integer" ? 1 : "any"} minLength={field.minLength} maxLength={field.maxLength} defaultValue={field.default == null ? "" : String(field.default)}/>}<small>{field.description}</small>
          </label>;
        })}</div>
        <details className="agent-inputs"><summary>Choose scoped evidence and accepted inputs</summary><p className="section-description">Pipeline prerequisites are included automatically. Choose additional records for this hypothesis. Missing evidence stays unknown.</p>
          {data.evidence.filter(e => !e.withdrawn && e.hypothesis_id === hypothesis).map(e => <label className="agent-check" key={e.id}><input name="evidence" value={e.id} type="checkbox"/><span>{e.title}<small>{e.id} · {e.consent}</small></span></label>)}
          {data.artifacts.filter(a => a.status === "ACCEPTED" && (agent === "passport" || spec.receives.includes(a.capability as Tool))).map(a => <label className="agent-check" key={a.id}><input name="artifact" value={a.id} type="checkbox"/><span>{a.title}<small>{a.capability} · accepted</small></span></label>)}
          {["experiment", "investor", "passport"].includes(agent) && data.experiments.filter(e => e.hypothesis_id === hypothesis).map(e => <label className="agent-check" key={e.id}><input name="experiment" value={e.id} type="checkbox"/><span>{e.title}<small>Locked protocol · {e.result.outcome}</small></span></label>)}
        </details>
        <RoutingControls spec={spec} catalog={catalog} mode={mode} setMode={setMode}/>
        <button className="button primary" disabled={busy || !hypothesis}>{busy ? "Saving…" : `Run ${spec.name}`}</button>
      </form>}
      {runs.map(run => <article key={run.id} className="agent-result"><div className="section-top"><h3>{run.objective}</h3><span className="status">{label(run.status)}</span></div>
        {run.error_code && <p className="error">{label(run.error_code)}. Correct the inputs or limits and run again.</p>}
        {["QUEUED", "RUNNING"].includes(run.status) && <p>Waiting for the local worker. This page refreshes while work is pending.</p>}
        {run.result.summary && <p>{run.result.summary}</p>}
        {run.result.evidence_class && <p className="source-location">{label(run.result.evidence_class)} · {run.result.mode} · ₹{run.cost_inr.toFixed(4)}</p>}
        {run.result.data && <details open={run.status === "AWAITING_REVIEW"}><summary>Specialist result</summary><Value value={run.result.data}/></details>}
        {!!run.result.unknowns?.length && <div><strong>Unknowns and required inputs</strong><ul className="unknown-list">{run.result.unknowns.map((u, i) => <li key={i}>{u}</li>)}</ul></div>}
        {run.result.next_action && <p><strong>Next action:</strong> {run.result.next_action}</p>}
        {!!run.result.limitations?.length && <ul className="unknown-list">{run.result.limitations.map((u, i) => <li key={i}>{u}</li>)}</ul>}
        <details><summary>Scoped context, provenance and tool trace</summary><Value value={{ sources: run.result.evidence_ids, context: run.context, trace: run.trace, result_hash: run.result_hash }}/></details>
        {run.status === "AWAITING_REVIEW" && <form onSubmit={e => void review(e, run)}><label>Founder decision<select name="choice"><option value="accept">Accept and create handoffs</option><option value="reject">Reject and stop this stage</option></select></label><label>Review rationale<textarea name="rationale" required minLength={10} maxLength={4000} rows={2} placeholder="Explain what you accept, its limits, and your next commitment."/></label><button className="button primary" disabled={busy}>Record specialist review</button></form>}
        {["QUEUED", "RUNNING", "AWAITING_REVIEW", "NEEDS_INPUT", "FAILED"].includes(run.status) && <button className="text-button danger" disabled={busy} onClick={async () => { setBusy(true); try { await command(`/agent-runs/${run.id}/cancel`, {}); } catch (e) { setError(e instanceof Error ? e.message : "Cancellation failed."); } finally { setBusy(false); } }}>Cancel run</button>}
        {run.artifact_id && <p className="source-location">Passport artifact: {run.artifact_id}</p>}
      </article>)}
      <p className="section-description">Available handoffs after acceptance: {spec.sends.map(id => catalog.agents.find(a => a.id === id)?.name || id).join(" → ") || "Passport record"}.</p>
    </>}
  </section>;
}

export function Pipelines({ passport, onSaved }: { passport: Passport; onSaved: (p: Passport) => void }) {
  const { catalog, error: catalogError } = useCatalog(); const [error, setError] = useState(""), [busy, setBusy] = useState(false), [selected, setSelected] = useState<string | null>(null);
  const data = agentRecords(passport); const base = `/ventures/${passport.venture.id}`;
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const f = new FormData(event.currentTarget);
    try { onSaved(await api<Passport>(base + "/pipelines", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ template: f.get("template"), objective: f.get("objective"), hypothesis_id: f.get("hypothesis_id"), expected_revision: passport.venture.revision }) })); }
    catch (e) { setError(e instanceof Error ? e.message : "Pipeline could not be created."); } finally { setBusy(false); }
  }
  return <div className="tools-area"><section className="card"><span className="eyebrow">THIRTEEN SPECIALISTS · ONE PASSPORT</span><h2>Choose a connected journey</h2><p className="section-description">Each stage uses scoped inputs and bounded tools. Review its exact output to unlock the next specialists. Independent branches can proceed together.</p>{(error || catalogError) && <p className="error" role="alert">{error || catalogError}</p>}{catalog && <form onSubmit={create}><label>Pipeline<select aria-label="Pipeline" name="template" defaultValue="complete">{catalog.templates.map(t => <option key={t.id} value={t.id}>{t.name} · {t.stages.length} specialists</option>)}</select></label><label>Pipeline objective<textarea name="objective" required minLength={10} maxLength={2000} placeholder="Describe the decision and evidence this journey should produce." rows={2}/></label><label>Linked hypothesis<select name="hypothesis_id">{passport.hypotheses.map(h => <option key={h.id} value={h.id}>{h.statement}</option>)}</select></label><button className="button primary" disabled={busy}>Create connected pipeline</button></form>}</section>
    {data.pipelines.map(p => <section className="card" key={p.id}><div className="section-top"><div><span className="eyebrow">{p.name}</span><h2>{p.objective}</h2></div><span className="pill">{p.status} · {p.stages.filter(s => s.status === "ACCEPTED").length}/{p.stages.length}</span></div><div className="pipeline-grid">{p.stages.map((s, i) => <button key={s.id} className={`pipeline-stage ${selected === s.id ? "selected" : ""}`} onClick={() => setSelected(selected === s.id ? null : s.id)}><span className="eyebrow">{String(i + 1).padStart(2, "0")} · {label(s.status)}</span><strong>{catalog?.agents.find(a => a.id === s.agent_id)?.name || s.agent_id}</strong><small>After: {s.dependencies.join(", ") || "Start"}</small></button>)}</div>{p.stages.filter(s => s.id === selected).map(s => <AgentConsole key={s.id} agent={s.agent_id} stage={s} pipeline={p} passport={passport} onSaved={onSaved}/>)}</section>)}
    <section className="card"><div className="section-top"><h2>Reviewed handoff ledger</h2><span className="pill">{data.handoffs.filter(h => h.status === "AVAILABLE").length} available</span></div>{!data.handoffs.length ? <p className="section-description">Accepted specialist results will appear here with their source run and destination.</p> : <div className="handoff-ledger">{data.handoffs.map(h => <div key={h.id}><strong>{catalog?.agents.find(a => a.id === data.agent_runs.find(r => r.id === h.from_run_id)?.agent_id)?.name || "Specialist"} → {catalog?.agents.find(a => a.id === h.to_agent_id)?.name || h.to_agent_id}</strong><span className="status">{h.status}</span><small>Artifact {h.artifact_id}</small></div>)}</div>}</section>
  </div>;
}
