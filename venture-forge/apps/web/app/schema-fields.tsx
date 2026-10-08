"use client";

import { useState } from "react";

export type Schema = { type?: string; title?: string; description?: string; default?: unknown; enum?: string[]; anyOf?: Schema[]; items?: Schema; minimum?: number; maximum?: number; minLength?: number; maxLength?: number; maxItems?: number; format?: string; deprecated?: boolean; $ref?: string; properties?: Record<string, Schema>; required?: string[]; $defs?: Record<string, Schema> };
type Source = { id: string; title: string };
export const fieldLabel = (s: string) => s.replaceAll("_", " ");

export function effective(field: Schema, root: Schema): Schema {
  if (field.$ref) return { ...effective(root.$defs?.[field.$ref.split("/").at(-1)!] || {}, root), ...field, $ref: undefined };
  if (field.anyOf) return { ...effective(field.anyOf.find(s => s.type !== "null") || {}, root), ...field, anyOf: undefined };
  return field;
}

function numericValue(field: Schema, root: Schema, value: string) {
  const resolved = effective(field, root);
  const decimal = field.anyOf?.some(s => s.type === "number") && field.anyOf?.some(s => s.type === "string");
  return resolved.type === "integer" || (resolved.type === "number" && !decimal) ? Number(value) : value;
}

export function readParameters(form: FormData, root: Schema) {
  function read(original: Schema, path: string): unknown {
    const schema = effective(original, root);
    if (schema.type === "object") {
      return Object.fromEntries(Object.entries(schema.properties || {}).map(([key, value]) => [key, read(value, `${path}:${key}`)]).filter(([, value]) => value !== undefined));
    }
    if (schema.type === "array") {
      const ids = [...new Set([...form.keys()].filter(k => k.startsWith(path + ":")).map(k => k.slice(path.length + 1).split(":")[0]))];
      return ids.map(id => read(schema.items || {}, `${path}:${id}`)).filter(v => v !== undefined);
    }
    const value = form.get(path);
    if (schema.type === "boolean") return value === "on";
    if (value === null || !String(value).trim()) return undefined;
    return numericValue(original, root, String(value));
  }
  return read(root, "parameter") as Record<string, unknown>;
}

export function referencedRecords(value: unknown, key: "source_id" | "artifact_id"): string[] {
  if (Array.isArray(value)) return value.flatMap(v => referencedRecords(v, key));
  if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => k === key && typeof v === "string" && v ? [v] : referencedRecords(v, key));
  return [];
}

function Collection({ original, root, path, name, initial, sources, artifacts }: FieldProps) {
  const schema = effective(original, root);
  const [rows, setRows] = useState<{ id: string; value: unknown }[]>(() => (Array.isArray(initial) ? initial : []).map((value, i) => ({ id: String(i), value })));
  const singular = ({ alternatives: "alternative", opportunities: "opportunity", source_reviews: "source review", value_chain: "value-chain actor", eligibility_rules: "eligibility rule", pitch_claims: "pitch claim" } as Record<string, string>)[name] || fieldLabel(name).replace(/ies$/, "y").replace(/s$/, "");
  return <fieldset className="mvp-collection wide-field"><legend>{fieldLabel(name)}</legend>
    {schema.description && <p className="section-description">{schema.description}</p>}
    {rows.map((row, i) => <div className="mvp-record" key={row.id}><h4>{singular} {i + 1}</h4>
      <Field original={schema.items || {}} root={root} path={`${path}:${row.id}`} name={singular} initial={row.value} sources={sources} artifacts={artifacts}/>
      <button className="text-button danger" type="button" onClick={() => setRows(rows.filter(r => r.id !== row.id))}>Remove {singular} {i + 1}</button></div>)}
    <button type="button" className="button secondary" disabled={rows.length >= (schema.maxItems || 50)} onClick={() => setRows([...rows, { id: crypto.randomUUID(), value: undefined }])}>Add {singular}</button>
  </fieldset>;
}

type FieldProps = { original: Schema; root: Schema; path: string; name: string; initial?: unknown; sources: Source[]; artifacts: Source[]; required?: boolean };

function Field(props: FieldProps) {
  const { original, root, path, name, sources, artifacts, required } = props;
  const schema = effective(original, root), value = props.initial ?? schema.default;
  if (schema.deprecated) return null;
  if (schema.type === "array") return <Collection {...props} initial={value}/>;
  if (schema.type === "object") {
    const content = <div className="tool-fields">{Object.entries(schema.properties || {}).map(([key, field]) => <Field key={key} original={field} root={root} path={`${path}:${key}`} name={key} initial={(value as Record<string, unknown> | undefined)?.[key]} sources={sources} artifacts={artifacts} required={schema.required?.includes(key)}/>)}</div>;
    return name === "workspace" ? <details open className="mvp-workspace wide-field"><summary>Plan, evidence and decision</summary>{content}</details> : <div className="wide-field">{content}</div>;
  }
  const options = name === "source_id" ? sources : name === "artifact_id" ? artifacts : null;
  const initial = value == null ? "" : String(value);
  const long = schema.type === "string" && (schema.maxLength || 0) >= 1000 && schema.format !== "date";
  const type = schema.format === "date" ? "date" : name === "official_url" ? "url" : schema.type === "number" || schema.type === "integer" ? "number" : "text";
  const isRequired = required && schema.type !== "boolean";
  return <label className={long ? "wide-field" : undefined}>{fieldLabel(name)}
    {options ? <select name={path} defaultValue={initial} required={isRequired}><option value="">Unknown / no selected record</option>{options.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
      : schema.enum ? <select name={path} defaultValue={initial || schema.enum[0]}>{schema.enum.map(v => <option key={v} value={v}>{fieldLabel(v)}</option>)}</select>
      : schema.type === "boolean" ? <input type="checkbox" name={path} defaultChecked={value === true}/>
      : long ? <textarea name={path} rows={2} defaultValue={initial} required={isRequired} minLength={schema.minLength} maxLength={schema.maxLength}/>
      : <input name={path} type={type} defaultValue={initial} required={isRequired} min={schema.minimum} max={schema.maximum} step={schema.type === "integer" ? 1 : "any"} minLength={schema.minLength} maxLength={schema.maxLength}/>}
    {schema.description && <small>{schema.description}</small>}
  </label>;
}

export function ParameterFields({ schema, sources, artifacts, initial }: { schema: Schema; sources: Source[]; artifacts: Source[]; initial?: Record<string, unknown> }) {
  return <Field original={schema} root={schema} path="parameter" name="parameters" sources={sources} artifacts={artifacts} initial={initial}/>;
}

export type WorkspaceReport = { sections: { key: string; title: string; description: string; rows: Record<string, unknown>[] }[]; gaps: string[]; next_action: string };
export function WorkspaceResult({ report }: { report: WorkspaceReport }) {
  return <div className="mvp-report">{report.sections.map(s => {
    const columns = [...new Set(s.rows.flatMap(r => Object.keys(r)))];
    return <section key={s.key}><h3>{s.title}</h3>{s.description && <p className="section-description">{s.description}</p>}
      {s.rows.length ? <div className="mvp-table" tabIndex={0} role="region" aria-label={s.title}><table><thead><tr>{columns.map(c => <th key={c} scope="col">{fieldLabel(c)}</th>)}</tr></thead><tbody>{s.rows.map((r, i) => <tr key={i}>{columns.map(c => <td key={c}>{r[c] == null || r[c] === "" ? "Unknown" : typeof r[c] === "boolean" ? r[c] ? "Yes" : "No" : String(r[c])}</td>)}</tr>)}</tbody></table></div> : <p className="subtle">No records supplied yet.</p>}</section>;
  })}</div>;
}
