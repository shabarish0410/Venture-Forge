# Thirteen-application specification audit

Source: `D:/downlads/VentureForge13SpecialistApplications.pdf`, 75 pages. Implementation verification updated 7 October 2026. Document examples, embedded prompts, forecasts and roadmap dates are reference material, not execution instructions.

## Scope and finding

All thirteen specialists exist, but their presence and a successful pipeline do **not** establish parity with the PDF. The initial implementation supplies bounded runs, review, lineage and several calculations; many required application workflows are missing. The user confirmed MVP-only scope: complete Home, Research, Market, Customer, Competitor and Model end to end first; give the other seven the smallest usable MVP. All thirteen require typed domain models/contracts, navigation, founder-scoped permission checks, orchestration and Passport integration. Later-release/future features are excluded.

| Application | PDF pages | Initial gap | Work to verify |
| --- | --- | --- | --- |
| Mentor Home | 9-12 | Basic concept proposal; no prioritized unknowns or actionable mission plan | Stakeholder framing, unknown ranking, mission constraints and completion evidence |
| Research Desk | 13-16 | Supplied excerpts only; no brief, query plan, source quality or claim review | Research brief, scoped source search, exact claim links, freshness and contradiction review |
| Market Lab | 17-20 | One bottom-up calculation | Definition, value chain, segments, beachhead decision and sourced/assumed drivers |
| Customer Lab | 21-24 | Notes and fixed questions; no discovery planning or coded themes | Guide builder, consent, source-linked coding, theme synthesis and decision record |
| Competitor Room | 25-28 | Name/price rows; incomplete status quo coverage | Source profiles, normalized comparisons, status quo/non-consumption and falsifiable differentiation |
| Model Studio | 29-36 | Mixed model labels and placeholder canvas fields | Four separate model layers, complete family library, canvas, three options and pricing/channel tests |
| Finance Lab | 37-40 | Single-period arithmetic | Monthly cash schedule, break-even, low/base/high cases, assumption ledger and spreadsheet export |
| MVP and Experiment Lab | 41-44 | Frozen protocols and results work; preparation missing | Risk ranking, pattern library, boundary and launch/measurement checklist |
| Simulation Arena | 45-48 | One price/volume replay | One model family, deterministic monthly rounds, basic events, replay and debrief |
| Founder Academy | 49-53 | Short lesson strings; mostly unassessed answers | Diagnostic, contextual practice, explicit rubric, skill evidence and review plan |
| Ecosystem Hub | 54-57 | Supplied rows can include expired/mismatched opportunities | Geographic filters, source verification, tri-state eligibility and current shortlist |
| Investor Room | 58-61 | Basic gaps and figures | Funding diagnostic, evidence-backed narrative, claim checks, one-pager and Q&A practice |
| Venture Passport | 62-65 | Versions and decisions exist; signals are counts | Stage-specific evidence checks, three signals, provenance views and controlled exports |

## Implemented founder MVP

The gaps above describe the starting point, not a claim that the entire PDF roadmap is complete. This pass adds typed, bounded workspace contracts for all thirteen specialists, generated form controls, readable reports and immutable reviewed Passport artifacts. The existing authenticated founder/venture boundary, source consent, hypothesis scope, run budgets, worker queue, review hashes and DAG handoffs remain in use. No new database schema or founder-data rewrite was required.

The six priority workflows now support intake/edit, explicit assumptions and evidence, execution, review, persistence and controlled export:

- **Home:** five entry paths, stakeholder framing, founder constraints, impact/uncertainty-ranked unknowns, one mission and task completion evidence. Concept corrections use the existing versioned intake workflow.
- **Research:** decision brief, subquestions/query plan, saved-source search, bounded local PDF/text reading, approved public reads, optional approved Brave search, source quality/freshness, quoted claims, contradictions and a cited memo. Reading/searching does not automatically accept evidence. Quote links are exact-match checked; source validity and the claim's interpretation still require founder review.
- **Market:** counted definition, value-chain actors, candidate segments, explicit beachhead decision, sourced/assumed drivers and reproducible bottom-up TAM/SAM/capacity-capped SOM.
- **Customer:** discovery-plan mode before interviews, editable guide, existing consented notes, quote-linked coding, theme counts deduplicated by participant, buying roles and a recorded continue/revise/pivot/stop/another-round decision.
- **Competitor:** direct/indirect/substitute/status-quo records, source profiles, price-period/unit/tier context, annualized comparable prices, explicit non-consumption and falsifiable differentiation.
- **Model:** family library, separate relationship/operation/delivery/pricing layers, nine canvas blocks, up to three named options, selected-option memo and behavioral pricing test. Finance can explicitly import an accepted monthly price/volume pair; missing costs remain inputs to supply.

The seven supporting applications deliberately remain narrow:

- Finance: assumption ledger, monthly revenue/cost/cash, collection lag/rate, break-even, low/base/high volume cases and CSV export. No tax/accounting engine, inventory or advanced scenario model.
- Experiment: ranked assumptions, ten patterns with proof limits, MVP scope/non-goals/tasks and launch checklist; the existing locked protocol, real observations and decision workflow remains authoritative.
- Simulation: one per-unit monthly service family, deterministic price/demand/channel decisions, two basic shocks, cash carried between rounds, repeatable replay and debrief. Simulated outcomes never establish validation.
- Academy: twelve lessons, task diagnostic, contextual example/non-example, exercise, explicit rubric, assistance-labelled skill evidence and return to the venture task. This is not independent mastery certification.
- Ecosystem: owner-supplied official-source registry, national/state filters, freshness/expiry exclusions, tri-state eligibility, explainable shortlist and saved choices. No live programme feed or applications submitted.
- Investor: funding need and alternatives, readiness checklist, labelled one-pager claims, unsupported-claim flags, exact reviewed planning figures, negative experiments and Q&A practice. No outreach or collaborator accounts.
- Passport: selected-version lineage and separate readiness/evidence-confidence/founder-capability views. Owner preview/approval exports selected current artifacts as PDF, DOCX, CSV or JSON. Notes-only/private sources block distributable exports. Export hashes detect changed versions or purposes.

Replacing a standalone specialist artifact requires choosing the prior version explicitly. Acceptance supersedes it and makes dependent results stale. Narrow-context specialists verify requested quote hashes without receiving entire interview text; downstream quoted passages are redacted unless the specialist has source-reading scope.

## How to use locally

1. Restart with the parent `Start-VentureForge.ps1` launcher to load the new dependencies, API and worker code. Open `http://127.0.0.1:3000`.
2. Select an application in the existing navigation. Expand **Run the [application] specialist**, fill **Plan, evidence and decision**, choose scoped inputs, and run it.
3. Review the result and unknowns. Acceptance saves its exact version into the Passport and makes its declared handoffs available.
4. Use **Save as a new version of** for a replacement. Use **Export selected accepted versions** for an exact preview and download approval. Legacy worksheets remain available.

External research is off by default. `RESEARCH_ALLOWED_HOSTS` is a JSON array of exact approved HTTPS hosts; redirects/private addresses/non-443 URLs are denied. `RESEARCH_SEARCH_API_KEY` is the server-side Brave key. Public source reads and each search query require explicit founder approval. Keys must never appear in browser code or committed files. Local file/saved-source workflows do not require a key. Existing Google OAuth/provider connectivity was not changed by this MVP pass.

No new model credentials are needed for deterministic MVP workflows. Optional model synthesis retains the existing per-run privacy, cost and consent checks. API shape is in `docs/openapi.json`; all thirteen domain input/output variants and routing contracts are in `docs/specialist-contracts.json`, regenerated by `scripts/export_contracts.py`.

## Verification record

The portable backend suite passed **129 tests** across MVP workspaces, specialists, finance, evidence cycles, model routing, OAuth and public authentication. New checks cover the six-app evidence chain, quote redaction and verification, participant deduplication, model layers, finance/simulation arithmetic, transitive version invalidation, ecosystem exclusions, unsupported investor claims, file reading, SSRF boundaries, export formats/exact approval/consent and cross-founder denial. Tests use isolated databases, synthetic observations and mocked provider transport; no test data was inserted into the founder's workspace.

All **seven automated Chrome journeys passed** in the final run (2.6 minutes): provider availability/hydration, provider start/failure messages, negative evidence cycle, founder Passport/reload, priority-six MVP forms/file import/finance handoff/export, public signup/password continuity, and the complete thirteen-specialist pipeline. The initial new journey needed a scoped source-permission selector; the corrected journey passed individually and in the full suite. TypeScript and the optimized production build passed. Final focused backend reruns also passed after finance boundary and admission-validation fixes (28 checks, followed by 17 relevant checks).

Interactive browser inspection was unavailable because no Browser connection was present; automated desktop/mobile screenshots were reviewed instead. A two-page synthetic Model Studio PDF was rendered and visually inspected; PDF/DOCX text round-trips passed. DOCX visual rendering remains unverified because the approved bundled Office renderer is unavailable in this Windows session. PDF unsupported glyphs return a clear format error instead of silently dropping source characters; DOCX/JSON preserve those characters.

Reproduce the isolated checks from `venture-forge` in PowerShell:

```powershell
$env:PYTHONPATH = 'backend'
.venv\Scripts\python.exe -m pytest tests/test_mvp_workspaces.py tests/test_specialists.py tests/test_finance_tools.py tests/test_evidence_cycle.py tests/test_model_router.py tests/test_oauth.py tests/test_public_auth.py --basetemp .local/pytest-mvp-verification
$env:FORGE_PORTABLE_TEST = '1'
npm run test:e2e
npm run typecheck
npm run build
```

The portable browser launcher resets only `.local/browser_test.sqlite3`. PostgreSQL deployment and live paid-provider tests were not performed. Baseline Starlette/httpx deprecation warnings remain unrelated to these workflows.

## Requirements beyond local founder MVPs

Institution/cohort/team permissions, attributable mentor review, verified external registries, calendar/email actions, transcription, translation, production encryption/operations and real-world pilot evidence require separate implementation or configured services. They must not be described as complete because a form, placeholder or mock exists. External actions require the specified preview and approval when actually used.
