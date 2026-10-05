# Specialist execution (5 October 2026)

All thirteen Product specialists execute distinct deterministic tool plans through `product/agents/`. Five persisted DAG templates route accepted prerequisites and source lineage through founder review gates. Domain request/output schemas, result hashes, budgets, atomic claims, interruption detection and cancelled-result disposal are implemented. Context snapshots omit original interview text from economics. Changed concepts or withdrawn sources invalidate downstream results and handoffs transitively.

Each specialist declares vendor-independent requirements for reasoning, context, structured output and tool-call capability. The hybrid Model Router selects an enabled OpenAI, Anthropic, Gemini or optional Ollama profile using those requirements, actual context size, privacy policy and budget. Complex reasoning prefers a capable cloud profile; local-only requests exclude cloud. Keys remain server-side and each model run requires processing consent. Python executes all arithmetic, validation, scoring and workflow state changes. Model analysis is separately labelled and must pass schema/source validation and founder review before Passport acceptance. With no ready profiles, AUTO explicitly uses zero-cost deterministic tools. See the [hybrid model layer](model-routing.md).

Native provider tool loops, live search, programme feeds, cohort roles and Company OS remain unavailable. See [specialist contracts and journeys](specialist-pipelines.md).

Migrations 0003/0004 add scoped pipeline, stage, run and handoff records, plus worker claim time. The extension supersedes the older statements about model/agent availability in the historical architecture below.

## Earlier evidence-cycle architecture

The current app retains Next.js/TypeScript, FastAPI/Pydantic and SQLAlchemy/Alembic. PostgreSQL remains the deployment database; the supervised local launcher adds a separate SQLite database so the application can run without Docker.

Thirteen workspace views route to shared typed domain commands. New record tables are evidence_receipts, tool_artifacts, locked_experiments, experiment_observations, founder_decisions and workflow_runs. Records carry venture and owner scope. Observation links use compound foreign keys; participant/receipt uniqueness protects experiment denominators. Every write checks ownership, revision and idempotency.

One separate Python worker processes persisted QUEUED runs using bounded evidence rules. It produces source receipts, unknowns and next missions at zero model cost. It never invokes a model or external tool. The web app polls only while runs are pending. Production concurrency/recovery, provider calls and external side effects require further controls.

Experiment protocols have no update endpoint. Results compare recorded, valid observations against locked sample and threshold; failed instruments and deviations yield inconclusive results. Reviewed decisions preserve result snapshots. Consent withdrawal redacts current source views, marks dependencies stale and removes the associated cycle from valid cycle counts. Canonical originals remain private pending a separate retention/deletion implementation.

The earlier foundation architecture below remains for context; its future-milestone statements have been superseded by this extension where described above.


# Product Engine and Company OS

The customer-facing Product Engine and internal Company OS share only stateless infrastructure helpers and explicitly authorized integration events. Neither can assume the other's authority.

| Foundation component | Owner / boundary |
| --- | --- |
| `product/core`, `product/api` | Product founder records and commands |
| `company_os` | Reserved Company module, no active automation |
| `shared/auth` | Password/session primitives; Product sessions carry Product realm |
| `vf_product` PostgreSQL database | `vf_product` role only, plus local database administrator |
| `vf_company` PostgreSQL database | `vf_company` role only, plus local database administrator |
| `vf_product_test` | Disposable Product test records, guarded by test scripts |
| `/company-os` page | Static roadmap only; no Company data access |
| `/api/company/v1/*` | Explicitly unavailable in the Product API |

The shared local administrator can provision databases. Runtime code uses the restricted Product role. Future Company deployments inject only Company credentials. Removing `PUBLIC CONNECT` from the databases prevents ambient cross-database access.

Product APIs derive identity from an opaque session token stored hashed in PostgreSQL. Ownership filters and composite foreign keys bind hypotheses/activity to their venture and founder. Mutation schemas reject injected owner/status fields. New assertions remain unvalidated. Row locks serialize revision and idempotency checks.

`POST /ventures` creates the venture, first hypothesis, activity event and idempotency response transactionally. `POST /ventures/{id}/hypotheses` checks the current venture revision and commits the hypothesis, incremented revision, activity and response together. Reusing the same key/payload returns the original response; reusing the key with changed content is rejected.

The foundation has no semantic search, LLM call, agent routing or synthetic evidence. Planned Product capabilities are displayed as planned. Company roles become executable only after their C0-C5 gates.

Company C1 will require exact-payload approval, durable action claiming, idempotency and uncertain-outcome reconciliation before email sending. That prerequisite is independent of the later Product Beta schedule. The initial two-track plan does not authorize real outbound communications during development.
