# Tool-first build status

## Sign-in design

Public email/password signup and Google/GitHub authorization-code authentication share the existing founder/session/Passport architecture. The requested GET provider starts and existing origin-protected POST/link routes coexist. There is no application allowlist. Migration `0006` adds profile and login metadata, account status, onboarding status, session authentication metadata and shared database rate limits. Fresh installs, upgrades, rollback/reapplication and founder/identity/session/Passport preservation checks pass. Disabled accounts are denied; failed OAuth attempts preserve the existing session and Passport. Account Settings connects either provider and supports password setup/change with session revocation. Matching emails never silently link accounts. Provider credentials remain pending the [setup steps](sign-in.md); see the [public authentication implementation report](public-authentication.md).

The reported extension-added `crxlauncher` attributes are handled by root-only hydration suppression. A browser check injects both root attributes before hydration and verifies that no hydration warning appears. Verification passed **123 portable backend tests**, **six Chrome journeys**, TypeScript in the production build and the production build itself. Provider HTTP was mocked; Google ID-token tests used real RSA signatures. Desktop/mobile sign-in and registration screens were visually checked. Email signup, onboarding, password changes, sign-out and return to the same saved Passport passed in Chrome.

The glass authentication design keeps the original cream/mint/lavender background, hero copy and typography. A 540 px form emphasizes email, followed by secondary provider buttons and terms text. The email step leads to sign-in or explicit account creation. Keyboard submission, focus, password visibility, changing email and reduced motion remain supported. Styling and animation use scoped CSS and inline SVG without additional frontend dependencies. The local database was backed up before applying migration 0006; original columns and rows in all 30 existing non-transient tables matched the backup afterward. The API/web returned HTTP 200, and the existing founder could sign in, access account settings and all thirteen specialists, then sign out. Google and GitHub correctly report that credentials are still needed.

## Current specialist extension

All thirteen specialists from the later 75-page `VentureForge13SpecialistApplications.pdf` now execute distinct bounded tool plans with validated inputs/outputs, scoped snapshots and reviewed Passport artifacts. Five persisted pipeline templates include every specialist in the complete journey. Exact-hash founder reviews create handoffs and unlock dependencies. Source withdrawal and concept changes invalidate downstream records. Atomic job claims, late cancellation disposal and supervised interruption recovery are implemented.

Hybrid routing is the default. All thirteen specialists declare vendor-independent reasoning, context, structured-output and tool-call requirements. OpenAI, Anthropic, Gemini and optional local Ollama adapters are selected by task, privacy, context and budget. Complex tasks prefer capable cloud profiles; local-only requests never fall back to cloud. Arithmetic, validation, scoring and workflows remain Python tools. Source-linked model synthesis is separately labelled and validated, while keys stay server-side and processing requires per-run consent. The shipped profiles are disabled until configured; no live provider call was made. See [model setup and routing](model-routing.md).

Programmes, alternatives and observations require founder inputs; live feeds, native provider tool loops, institutional roles and external actions remain unavailable. See [specialist guide](specialist-pipelines.md).

FinancePilot, worksheets and simulation calculate CAC, revenue/gross-profit LTV, margin, runway, cash change and ending cash using Decimal functions. Optional customer inputs remain unknown when missing. Cost classification and month/year lifetime units are validated; finance output figures must match their recorded drivers. Browser specialist forms preserve decimal text without conversion to binary floats. The formulas and assumptions are documented in the [Finance Lab guide](finance-tools.md).

Migrations 0003/0004 add pipelines, stages, specialist runs, handoffs and claim time. Fifty-eight portable API tests pass, including all five journeys and thirteen specialists, review gates, scope, staleness, cancellation during execution, interruption recovery, four mocked provider transports, capability routing, local privacy, source quotes, cost/step admission, profile files, finance golden cases and preservation/rollback/drift. Synthesis tasks require synthesis, hypothesis assessment and verified claims when original text is available; generic explanations fail without promoting an artifact, while valid analysis cannot validate a hypothesis. All three isolated Chrome journeys pass: foundation, negative experiments and the full thirteen-stage pipeline. They cover hybrid defaults, configured privacy/consent controls through a public catalog fixture, customer metrics, decimal request preservation, desktop/mobile rendering and reload. TypeScript checking, regenerated API contracts and the production build pass. Live API/web health and the updated thirteen-agent catalog were verified after restart. Rival/programme records use entry forms and the handoff ledger scrolls inside its panel.

The application launcher applies migrations while preserving founder credentials and local data. SQLite is the verified local path. PostgreSQL/Docker and live-provider checks still require configured services. The historical build record below describes the earlier worksheet implementation; its statements about model/specialist availability are superseded by this extension.

## Earlier evidence-cycle build record

Updated 5 October 2026 (Asia/Kolkata).

The prior foundation has been extended to a persistent local evidence-to-decision application. The supplied 32-page PDF is design input. Its copyable "build only package A" example was not treated as an instruction to stop; the user's request controls the scope.

Implemented: thirteen workspace views, shared Passport, original source receipts and consent context, hypothesis links, queue/worker rule proposals, reviewed worksheets, deterministic market/finance/scenario tools, locked protocols, unique participants, real-observation links, quality gates, founder decisions, immutable snapshots, withdrawal propagation, current JSON export and an independent Docker-free local launcher.

Advanced capabilities use founder-entered worksheets, with their limitations stated in the UI. There are no fabricated sources, invented programme feeds, model calls, external actions or fake success scores. Record acceptance is separate from evidence status.

Migration 0002 adds the research metadata that was present in code but absent from migration 0001, and the new workflow tables. The migration is additive; the portable suite checks rollback/reapplication and metadata drift. Take a database backup before downgrading: a downgrade removes the new records.

The old Agents Office tree is retained in the parent `archive/` ZIP with its original notices. All 121 archived files passed byte count and SHA-256 verification before 32 old root entries were removed. Founder databases, credentials, the new app repository and dependency folders were preserved.

Local validation completed:

- Eight portable API regression tests passed, including negative results, consent, source withdrawal, stale versions, duplicate observations, ownership, injected source instructions, invalid arithmetic and migration rollback/reapplication/drift.
- Both browser journeys passed in isolated Chrome: the original sign-in/hypothesis flow, and all thirteen tools with a locked negative experiment, founder decision, queued rule review, financial golden case, JSON export and reload.
- TypeScript checking and the optimized Next.js production build passed.
- Desktop Home, Finance and Experiment screens plus the 390px Customer screen were visually inspected. The browser suite reported no uncaught page errors or horizontal overflow.
- The local launcher started API, worker and web successfully. API health and web returned successful responses. Founder data starts empty; synthetic browser records live only in the separate test database.

The first browser attempt required a decision-selector correction, then both journeys passed. Build/browser subprocesses required normal process permissions because sandboxed runs returned `spawn EPERM`; the approved local reruns passed.

PostgreSQL/Docker validation depends on a running Docker daemon; it was unavailable during this build. Portable SQLite checks do not establish PostgreSQL RLS or production readiness. The original PostgreSQL CI suite remains configured but was not run remotely.
