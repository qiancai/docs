---
name: tidb-doc-e2e-test
description: End-to-end test TiDB and TiDB Cloud documentation by verifying that a user following the doc can complete the task — unified protocol (predict, observe, compare, act, verify, record), two-layer routing by environment and execution method, semantic snapshot diff for UI drift, SQL harness for both playgrounds and Cloud instances. Use when testing docs examples/flows in pingcap/docs (SQL statements, functions, features, quickstarts) or TiDB Cloud docs (console UI, SQL, REST API specs from the idl repo).
---

# TiDB Doc E2E Test

Use this skill when the task is to test a TiDB or TiDB Cloud documentation page against a live environment, detect documentation drift, or run doc regression. The question being answered is always: **can a user following this document complete the task?**

## Architecture principle (non-negotiable)

**The documentation agent is the single reasoning and verdict layer.** Every tool layer only exposes state and executes actions — no tool decides on its own how to adapt to environment or UI changes.

```
Documentation Agent (SINGLE REASONER)
    │ decide / compare / judge
    ├── Browser control: Playwright MCP / Browser Use CLI (CDP)
    ├── SQL: scripts/run-sql-test.py (any TiDB endpoint)
    ├── REST API: scripts/api_orchestrator.py (TiDB Cloud API)
    ├── Diagnostics: Chrome DevTools MCP (console/network only)
    └── Environment: tiup playground / TiDB Cloud org
```

Rules that protect finding accuracy:

- **Self-healing is permitted; silent self-healing is not.** You may retry with a different selector or endpoint to keep the task track alive, but every adaptation MUST be logged as a candidate drift finding.
- **API/CLI state is the fact layer; UI is the narrative layer.** Assert resource state via API or SQL. Use UI observation only for what the doc promises a user will see.
- **Full observations go to disk; only deltas enter context.** Never let raw dumps flood the conversation.

## The test protocol (run per document step)

1. **PREDICT** — extract from the doc step what the user should see/get: page name, button labels, default values, expected output or outcome text. Write it down before observing.
2. **OBSERVE** — observe each state exactly once, with the cheapest tool that carries full state.
3. **COMPARE** — check the prediction against the observation explicitly, line by line. Never eyeball.
4. **ACT** — perform the action like a user would. On failure, see the self-healing rule above.
5. **VERIFY** — poll for the resulting state; avoid fixed sleeps except as a last resort.
6. **RECORD** — full snapshot to file; only the delta (vs prediction or baseline) enters context; screenshots as evidence at checkpoints and anomalies only.

## Routing: two layers, never bind product to tool

**Layer 1 — target environment.** Determine: TiDB or TiDB Cloud; use an existing environment or validate a create/deploy flow; **version** and scope. Version is a test input: TiDB docs are tested against an instance of the matching version; Cloud docs consider both the release branch and current service behavior. A version mismatch is recorded explicitly — it is never silently filed as a doc error.

**Layer 2 — execution method.** Browser / SQL / REST API / Shell-CLI. One doc may combine several methods; test each part on its own method and merge findings into one report.

Load the matching reference file only when needed:

| Environment | Reference file | Covers |
|---|---|---|
| TiDB (self-hosted) | `ref-tidb.md` | playground lifecycle, version alignment, environment tiers, phase scope |
| TiDB Cloud | `ref-tidb-cloud.md` | console login/org checks, browser pitfalls, REST API specs |

## Scope

Covering both products does NOT mean supporting every operation on day one.

- **Phase 1 (supported)**: SQL examples on both products; TiDB Cloud console UI flows; TiDB Cloud REST API spec-vs-live checks.
- **Later phases (need dedicated flows first)**: TiUP deployment/upgrade, backup & restore, disaster recovery drills, ticloud CLI. If a doc needs one of these, mark the step `NOT-COVERED` and flag the gap — do not improvise.

**Reference docs are not blindly runnable.** System variable references, SQL statement pages, and similar often contain mutually exclusive examples, expected-error examples, and independent scenarios. Partition such pages into test cases with preconditions first; never execute the whole file top to bottom without that partitioning. (`scripts/scan-sql-blocks.py` produces the block inventory to plan this.)

## Verdict taxonomy

Every finding lands in exactly one bucket — never collapse them:

| Verdict | Meaning |
|---|---|
| `PASS` | Observed behavior matches the doc |
| `DOC-DISCREPANCY` | Product behaves normally but differs from the doc → candidate doc fix |
| `PRODUCT-ANOMALY` | Product itself misbehaves regardless of the doc → not a doc bug; report separately |
| `VERSION-MISMATCH` | Environment version/edition differs from what the doc targets → record, do not judge the doc |
| `ENV-BLOCKED` | Test could not run (login expired, quota, network) → retry after fixing; never counts as pass or fail |
| `NOT-COVERED` | Step not testable with currently supported flows → flag the gap |

Adjudication rules:

- An API/console/SQL error is NOT automatically doc drift — it may be a product anomaly, a version mismatch, or an environment problem. Classify first, blame the doc last.
- A selector retry does NOT automatically mean the UI text changed — only the observed end state counts as evidence.

## Baselines and cleanup

- A baseline is bound to: **doc file + commit hash, environment (org/role or instance/version), language, checkpoint**. Store under `.tmp/baselines/<doc-path-hash>/<checkpoint>.snap` with a sidecar recording these bindings.
- **A first-pass run that produced findings can never become the known-good baseline.** Baselines come only from runs with zero unresolved discrepancies, or from a human verdict accepting the new state.
- Cleanup must use **resource IDs recorded at creation time**, not name lookup. Log every created resource ID in the report. "Using an existing environment" and "created during the test" have different cleanup boundaries — see the reference files.

## Typical invocation

> "Use tidb-doc-e2e-test to check document X on test cluster Y."

The skill identifies the doc's product, checks version alignment, and selects the flows. Ask the user only when information that would change execution is missing (credentials, version, whether an existing instance may be mutated).

## Report format

Write every test report in **English** to `.tmp/test-reports/<date>-<doc-name>.md` with: header (doc, environment incl. version, instance, date), verdict, per-step table (doc step / actual result / verdict from the taxonomy), issues ranked by severity with human-verdict flags, resource IDs created and cleaned up, infrastructure learnings, cleanup confirmation.

## Scripts

- `scripts/run-sql-test.py` — SQL-doc harness: extract `sql` blocks, execute them in document order over ONE shared connection (session state carries), compare with documented expected output (exact / weak / smoke). Works for local playground and TiDB Cloud Starter alike. Mislabeled output blocks (result tables tagged as sql) are auto-detected.
- `scripts/snapdiff.py` — normalize two a11y snapshots and diff (strip refs, mask high-entropy values only, drop proven-volatile lines only; content-only compare + order fallback).
- `scripts/observe_page.py` — filtered AX-tree observation for Browser Use CLI; output format is snapdiff-compatible, includes form values and control states.
- `scripts/api_orchestrator.py` — TiDB Cloud serverless v1beta1 API helper: wait for ACTIVE, delete by clusterId, run SQL; `--dry-run` covers all side effects.
- `scripts/scan-sql-blocks.py` — repo inventory: count SQL blocks per doc, classify statement types, flag environment dependencies, score automatability.
