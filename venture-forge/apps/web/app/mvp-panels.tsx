"use client";

import { useState, type FormEvent } from "react";
import { api, type Passport } from "@/lib/api";
import { records } from "./tools";
import { WorkspaceResult, type WorkspaceReport } from "./schema-fields";

type ReadDocument = { filename: string; sha256: string; pages: { locator: string; text: string }[]; notice: string };

export function ResearchSources({ passport, onSaved }: { passport: Passport; onSaved: (p: Passport) => void }) {
  const base = `/ventures/${passport.venture.id}`;
  const [document, setDocument] = useState<ReadDocument | null>(null), [page, setPage] = useState(0);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [results, setResults] = useState<{ title: string; locator?: string; url?: string; content?: string }[]>([]);
  async function perform(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); } catch (e) { setError(e instanceof Error ? e.message : "Research request failed."); } finally { setBusy(false); }
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    await perform(async () => {
      if (file.size > 4 * 1024 * 1024) throw new Error("Choose a PDF or UTF-8 text file no larger than 4 MB.");
      const content = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.onerror = () => reject(new Error("Couldn't read the selected file.")); reader.readAsDataURL(file); });
      setDocument(await api<ReadDocument>(base + "/research/read-file", { method: "POST", body: JSON.stringify({ filename: file.name, content_base64: content }) })); setPage(0);
    });
  }
  async function source(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const f = new FormData(event.currentTarget);
    await perform(async () => { setDocument(await api<ReadDocument>(base + "/research/read-source", { method: "POST", body: JSON.stringify({ url: f.get("url"), approved: f.get("approved") === "on" }) })); setPage(0); });
  }
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const f = new FormData(event.currentTarget);
    await perform(async () => {
      if (f.get("web") === "on") {
        const result = await api<{ results: typeof results }>(base + "/research/web-search", { method: "POST", body: JSON.stringify({ query: f.get("query"), approved: true }) }); setResults(result.results);
      } else {
        const result = await api<{ sources: typeof results }>(base + "/research/sources?q=" + encodeURIComponent(String(f.get("query")))); setResults(result.sources);
      }
    });
  }
  async function capture(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const f = new FormData(form);
    await perform(async () => {
      const result = await api<Passport>(base + "/evidence", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ expected_revision: passport.venture.revision, hypothesis_id: f.get("hypothesis_id"), title: f.get("title"), content: f.get("content"), locator: f.get("locator"), limitations: f.get("limitations"), collected_on: f.get("collected_on"), relation: f.get("relation"), consent: f.get("consent"), kind: "source" }) });
      onSaved(result); setDocument(null);
    });
  }
  return <section className="card"><h2>Research sources and document reader</h2><p className="section-description">Find a source, read it, then register an exact passage. Search results alone do not support claims.</p>
    {error && <p className="error" role="alert">{error}</p>}
    <form onSubmit={search}><label>Source search<input name="query" required minLength={3} maxLength={400}/></label><label className="agent-check"><input name="web" type="checkbox"/><span>Send this query to the configured web-search provider. Leave unchecked to search my saved sources.</span></label><button className="button secondary" disabled={busy}>Search sources</button></form>
    {!!results.length && <ul>{results.map((r, i) => <li key={i}><strong>{r.title}</strong>{r.url ? <p><a href={r.url} target="_blank" rel="noreferrer">Open original source</a></p> : <p>{r.locator}</p>}{r.content && <details><summary>Read saved passage</summary><p>{r.content}</p></details>}</li>)}</ul>}
    <div className="tool-fields"><label>Read a local PDF or text file<input type="file" accept=".pdf,.txt,.md,.csv" disabled={busy} onChange={e => void upload(e.target.files?.[0])}/><small>Up to 4 MB; text PDFs up to 100 pages. Extraction does not accept a claim.</small></label></div>
    <details><summary>Read an approved public website</summary><form onSubmit={source}><label>Public source URL<input type="url" name="url" required maxLength={2000}/></label><label className="agent-check"><input type="checkbox" name="approved" required/><span>I approve fetching this public URL for this research task.</span></label><p className="section-description">Website hosts must be configured in the server’s approved research sources.</p><button className="button secondary" disabled={busy}>Read public source</button></form></details>
    {document && <div className="mvp-reader"><h3>{document.filename}</h3><p>{document.notice}</p><label>Source page or section<select value={page} onChange={e => setPage(Number(e.target.value))}>{document.pages.map((p, i) => <option key={i} value={i}>{p.locator}</option>)}</select></label><details><summary>Original extracted text</summary><pre className="mvp-source-text">{document.pages[page].text}</pre></details>
      <form key={`${document.sha256}:${page}`} onSubmit={capture}><label>Linked hypothesis<select name="hypothesis_id">{passport.hypotheses.map(h => <option key={h.id} value={h.id}>{h.statement}</option>)}</select></label><label>Source title<input name="title" defaultValue={document.filename.slice(0, 300)} minLength={3} maxLength={300} required/></label><label>Page or section locator<input name="locator" defaultValue={document.pages[page].locator.slice(0, 2000)} maxLength={2000} required/></label><label>Exact selected passage<textarea name="content" defaultValue={document.pages[page].text.slice(0, 2000)} rows={6} minLength={10} maxLength={20000} required/></label><label>Source limitations<textarea name="limitations" rows={2} minLength={3} maxLength={2000} required/></label><label>Captured on<input type="date" name="collected_on" defaultValue={new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date())} required/></label><label>Relationship<select name="relation"><option value="contextualizes">Contextualizes</option><option value="supports">Supports</option><option value="contradicts">Contradicts</option></select></label><label>Source permission<select name="consent"><option value="private_observation">Private research only</option><option value="public_source">Public source with permitted use</option></select></label><button className="button primary" disabled={busy}>Register selected passage</button></form>
    </div>}
  </section>;
}

type Preview = { preview_hash: string; payload: { artifacts: { id: string; title: string; sections: WorkspaceReport["sections"]; gaps: string[] }[]; sources: { id: string; title: string; locator: string }[] } };

export function ControlledExport({ passport }: { passport: Passport }) {
  const [preview, setPreview] = useState<Preview | null>(null), [selection, setSelection] = useState<{ artifact_ids: string[]; purpose: string } | null>(null);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const accepted = records(passport).artifacts.filter(a => a.status === "ACCEPTED");
  const base = `/ventures/${passport.venture.id}/mvp-exports`;
  async function inspect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true); setPreview(null); const f = new FormData(event.currentTarget);
    const chosen = { artifact_ids: f.getAll("artifact").map(String), purpose: String(f.get("purpose")) };
    try { setPreview(await api<Preview>(base + "/preview", { method: "POST", body: JSON.stringify(chosen) })); setSelection(chosen); }
    catch (e) { setError(e instanceof Error ? e.message : "Preview failed."); } finally { setBusy(false); }
  }
  async function download(format: string) {
    if (!preview || !selection) return; setBusy(true); setError("");
    try {
      const response = await fetch("/api/v1" + base + "/download", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...selection, preview_hash: preview.preview_hash, format, approved: true }) });
      if (!response.ok) { const body = await response.json(); throw new Error(body.error?.message || body.detail?.message || "The export could not be generated."); }
      const url = URL.createObjectURL(await response.blob()); const a = window.document.createElement("a"); a.href = url; a.download = `venture-forge.${format}`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e instanceof Error ? e.message : "Download failed."); } finally { setBusy(false); }
  }
  return <section className="card"><h2>Preview and export reviewed work</h2><p className="section-description">Choose exact accepted versions for a stated purpose. Private and notes-only evidence is excluded from distributable packages. This downloads a file; it does not create a shared link.</p>{error && <p className="error" role="alert">{error}</p>}
    <form onSubmit={inspect}><label>Export purpose<input name="purpose" minLength={5} maxLength={300} required placeholder="For my next business-model review"/></label>{accepted.map(a => <label className="agent-check" key={a.id}><input type="checkbox" name="artifact" value={a.id}/><span>{a.title}<small>{a.capability} · {new Date(a.created_at).toLocaleDateString("en-IN")}</small></span></label>)}<button className="button secondary" disabled={busy || !accepted.length}>Preview selected export</button></form>
    {preview && <div><h3>Exact export preview</h3>{preview.payload.artifacts.map(a => <details key={a.id}><summary>{a.title}</summary><WorkspaceResult report={{ sections: a.sections, gaps: a.gaps, next_action: "" }}/></details>)}<p>{preview.payload.sources.length} source references included. Check the selected versions and source permissions before distributing the file.</p><div className="mvp-actions">{["pdf", "docx", "csv", "json"].map(f => <button type="button" className="button primary" key={f} disabled={busy} onClick={() => void download(f)}>Approve and download {f.toUpperCase()}</button>)}</div></div>}
  </section>;
}
