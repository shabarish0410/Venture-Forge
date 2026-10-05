import type { components } from "./contracts";
export type Passport = components["schemas"]["Passport"];
export type Founder = components["schemas"]["FounderView"];
export type VentureCreate = components["schemas"]["VentureCreate"];
export type HypothesisCreate = components["schemas"]["HypothesisCreate"];

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...options.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ApiError(Array.isArray(detail) ? "Please check the form fields and try again." : detail?.message || "We couldn't complete that request. Please try again.", response.status);
  }
  return response.status === 204 ? undefined as T : response.json();
}
