# Current status

The original foundation status below is historical. See [tool-first build status](build-status.md) for the current evidence-cycle implementation and validation.


# Foundation delivery record

Verified locally on 3 October 2026, Asia/Kolkata. VF-001 through VF-007 are implemented in the independent `venture-forge` repository. This is a supervised local foundation; Product V0 and Company C0-C5 are not active.

| Item | Delivered | Evidence |
| --- | --- | --- |
| VF-001 | Original repository, UI, schemas and provenance | Git initialized on `main`; [provenance](provenance.md); [direct dependency licenses](dependencies.md); no reference application modules/assets imported |
| VF-002 | PostgreSQL, explicit Alembic migration, test infrastructure, CI definition | Local migration/schema check; PostgreSQL-backed tests; `.github/workflows/checks.yml` |
| VF-003 | Local founder identity, hashed passwords, opaque sessions, expiry/logout, origin and ownership checks | Authentication, session expiry, wrong-owner API/database cases; Product/Company connection-denial tests |
| VF-004 | Validated API contracts and generated client types | `docs/openapi.json`, `apps/web/lib/contracts.ts`; contract regeneration and TypeScript check |
| VF-005 | Transactional venture/hypothesis commands, revisions, idempotency and activity | Unvalidated assertions; stale-write rejection; concurrent same-key retry produces one hypothesis |
| VF-006 | Mentor Home, onboarding, Passport, hypotheses, activity and current JSON download | Desktop and mobile browser rehearsal; screenshots inspected; labelled forms, dialog and focus styles |
| VF-007 | Synthetic end-to-end rehearsal | Sign in, create venture, add hypothesis, export, reload, mobile Company roadmap navigation and sign out |

## Local verification

- 12 PostgreSQL-backed tests passed: 10 foundation cases and two cross-database permission cases.
- Alembic reports no new upgrade operations: model metadata and the migration agree.
- OpenAPI and TypeScript contracts regenerate without drift.
- Type checking and the optimized Next.js production build passed.
- One full browser rehearsal passed using an isolated headless Chrome profile and disposable `vf_product_test` database. No browser errors or horizontal overflow at 390px viewport width.
- Screenshots inspected: onboarding and Mentor Home at 1440px, and Mentor Home at 390px. Local artifacts are in `.local/` and excluded from Git.
- Local credentials, browser traces, generated Next.js declarations and dependency/build directories are excluded from Git.

Next.js generates route declarations before standalone TypeScript checking, following its [CLI guidance](https://nextjs.org/docs/app/api-reference/cli/next#next-typegen-options). Its development indicator is hidden because it covered the mobile sign-out control; compilation and runtime error reporting remain available.

The CI workflow is written but has not run remotely. Keyboard/screen-reader auditing and production accessibility certification are not completed. These checks cover the foundation and do not replace the later Product mission, evidence, experiment or Company action evaluations.

## Runtime and scope

Local URL: `http://127.0.0.1:3000`. The Product API uses port 8010; PostgreSQL is restricted to loopback port 55432. Generated founder sign-in details are in `.local/sign-in.txt`; [README](../README.md) explains startup and shutdown.

The developer administrator provisions both databases. Product runtime credentials cannot connect to Company records, and Company credentials cannot connect to Product records. A Company runtime, credentials vault, CEO login, approval queue and agents are not implemented. Shared configuration in this local checkout is not a production secret-distribution mechanism.

Research, document ingestion, evidence, model calls, missions, customer interviews, experiments and founder decisions are the next Product V0 work. Current JSON download represents the live read model; immutable export snapshots come later. Founder accounts are bootstrapped locally; registration, password recovery, managed identity, multi-workspace grants and distributed login throttling are deferred.

No remote repository, deployment, external connector, email send, publication or scheduled task was created. The new Git repository is initialized without commits. Synthetic test records are separate from the initially empty founder workspace.
