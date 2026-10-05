# Venture Forge

A local founder workspace based on both supplied Venture Forge PDFs. Thirteen executable specialists share one Venture Passport and connect through five reviewed pipelines. A provider-agnostic hybrid router selects configured OpenAI, Anthropic, Gemini or optional Ollama profiles by task capability, privacy, context and budget. Calculations, validation and workflows run in code. Deterministic tools remain available without a provider account.

## Run on Windows

From the parent workspace, run:

```powershell
.\Start-VentureForge.ps1
```

Requires Python 3.11+ and Node 22+. The launcher installs missing dependencies, applies migrations and starts the API, one worker and the web app. Open **http://127.0.0.1:3000**, using private credentials in `.local/local-sign-in.txt`. The database is `.local/venture-forge.sqlite3`, separate from the existing PostgreSQL configuration. Existing founder passwords are preserved. Keep the terminal open; Ctrl+C stops services. Stop services before copying the database and credential file for a private backup.

New users can choose **Continue with email > Create account** to register. Google and GitHub create or sign into accounts after provider applications and server-side credentials are configured. There is no application allowlist. Account Settings connects providers or adds a password to the same founder and Venture Passport. Follow the [sign-in setup guide](docs/sign-in.md) for exact callbacks and console steps, and the [public authentication guide](docs/public-authentication.md) for deployment settings and migration 0006.

## The thirteen specialists

| Workspace | Specialist | Executable output |
| --- | --- | --- |
| Mentor Home | ForgeGuide | Concept Map, explicit unknown roles, bounded mission |
| Research Desk | EvidenceScout | Source-linked memo, claim ledger, contradictions and freshness |
| Market Lab | MarketMapper | Buying-unit definition and Decimal TAM/SAM/capped SOM |
| Customer Lab | CustomerLens | Consented observation ledger, denominators and interview guide |
| Competitor Room | RivalRadar | Alternatives, status quo, source-linked prices and switching test |
| Model Studio | ModelArchitect | Canvas, two relationship options and pricing test |
| Finance Lab | FinancePilot | Revenue, margin, cash and runway from explicit drivers |
| MVP and Experiment Lab | MVPForge | Draft protocol or review of locked experimental results |
| Simulation Arena | VentureSim | Replay of reviewed finance with labelled simulated price/volume changes |
| Founder Academy | SkillCoach | Twelve contextual lessons, applied practice and assistance record |
| Ecosystem Hub | EcosystemNavigator | Supplied programme shortlist, expiry, eligibility and verification gaps |
| Investor Room | InvestorRoom | Funding milestone, reconciled reviewed figures and diligence gaps |
| Venture Passport | PassportKeeper | Accepted version lineage; readiness, evidence and learning kept separate |

Open **Agent Pipelines** and choose **All thirteen specialists**, raw idea, pivot, learning or funding preparation. Open a ready stage, choose scoped records, supply its inputs, run it and review the exact result with a rationale. Accepted results create Passport artifacts and handoffs; dependent stages unlock after review. The specialist can also run independently from its own workspace. Existing worksheets and real experiment controls remain available.

See the [specialist pipeline guide](docs/specialist-pipelines.md) for journeys, recovery and model setup. Supplied source notes remain attributed observations; no live search or programme registry is connected.

The [hybrid model guide](docs/model-routing.md) explains per-agent requirements, cloud preference for complex tasks, local-only policy, source-linked synthesis and server-side profile/key configuration. Models are not hard-coded to specialists.

The [Finance Lab guide](docs/finance-tools.md) describes deterministic CAC, lifetime-value estimates, margins, runway and cash calculations. Missing customer inputs stay unknown; model explanations cannot replace the figures.

## Complete a learning cycle

1. Create the venture and a falsifiable hypothesis.
2. Predeclare the intervention, binary metric, threshold, minimum sample, end date and stop rule in Experiment Lab. Lock it before observing results.
3. Capture real, consented interviews in Customer Lab, preserving negative responses.
4. Append each receipt to the experiment once. Invalid instruments, deviations, missing samples and withdrawn receipts produce inconclusive outcomes.
5. Choose continue, revise or stop and record why. Adequately sampled negative results count as reviewed learning; inconclusive results do not count as completed cycles.
6. Export the Passport. Withdrawal redacts the current source view, makes dependent decisions stale and updates the reviewed-cycle count.

Source relationships are founder-labelled, not independently verified factual support. Withdrawal preserves private originals; it is not deletion or a retention workflow. Already downloaded copies cannot be recalled.

## PostgreSQL deployment

The prior PostgreSQL path remains supported. With Docker Desktop running Linux containers, from this directory:

```powershell
python scripts/setup_local.py
docker compose up -d --wait
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/bootstrap.py
```

Start in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn venture_forge.product.api.app:app --host 127.0.0.1 --port 8010
.\.venv\Scripts\python.exe -m venture_forge.product.worker
npm run dev
```

Use `.local/sign-in.txt` for this PostgreSQL founder. Do not run both modes on the same ports. `docker compose down` retains its named database volume. The workspace cleanup never touches database volumes.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_public_auth.py tests/test_oauth.py tests/test_evidence_cycle.py tests/test_specialists.py tests/test_model_router.py tests/test_finance_tools.py --basetemp .local/pytest-verification
.\.venv\Scripts\python.exe scripts/export_contracts.py
npm run contracts
npm run typecheck
npm run build
$env:FORGE_PORTABLE_TEST = '1'
npm run test:e2e
```

The portable API suite uses temporary SQLite files. Browser tests use `.local/browser_test.sqlite3`, synthetic accounts and ports 3001/8011; they never reset founder data. Without `FORGE_PORTABLE_TEST`, browser tests and the original foundation suite use the configured disposable PostgreSQL `_test` database. CI retains PostgreSQL checks.

## Operating boundary

This is a supervised local app. Argon2 sign-in, opaque sessions, same-origin writes, server-side ownership, scoped foreign keys, revision checks and idempotency are implemented. Hybrid routing is the default; model calls require enabled server profiles, private keys for cloud providers and per-run processing consent. Without ready profiles, deterministic tools remain available. Models receive no executable tool or Passport write access. External actions are unavailable.

Live search, email, payment, external sharing and file ingestion are not connected. PDF model names are design examples; the operator chooses the provider model. Company OS remains an inactive separate roadmap. Multi-tenant RLS, OIDC/MFA, reviewer/institution roles, managed secrets, encryption, deletion/legal holds, production backups and an external-action outbox require further work before cohort deployment.

One worker processes persisted queues. New specialist jobs use an atomic claim, discard cancelled late results and mark interrupted work failed after its time cap plus a two-minute recovery allowance; the founder can start a new run. Model requests are never automatically retried. The older evidence-review queue retains its earlier recovery limitations. Tool traces record policies, provenance and usage; hidden model reasoning is not captured.

See [build status](docs/build-status.md), [architecture](docs/architecture.md) and [provenance](docs/provenance.md).
