---
name: tidb-doc-e2e-test
description: Validate existing TiDB and TiDB Cloud documentation through document consistency checks, source-code verification for the target version, and live environment tests. Use when auditing important merged docs or testing SQL examples, system variables, features, quickstarts, console flows, and API documentation. Select evidence per claim or step and report runtime coverage explicitly.
---

# TiDB Doc E2E Test

Use this skill to validate existing TiDB or TiDB Cloud documentation, detect documentation drift, or run doc regression. The question being answered is always: **can a user following this document complete the task?** Use document checks, source verification, and runtime tests as appropriate; report which parts were actually executed.

## Scope and starting points

- **Core runtime scope**: partitioned SQL examples on local TiDB or TiDB Cloud Starter, and Starter API spec-vs-live checks. Document and source checks can proceed independently of runtime coverage.
- **Conditional runtime scope**: Starter console flows with an available browser and an existing authenticated account; instance creation only within the established authorization and spending limit $0.
- **Not yet supported by default**: account signup, paid Cloud operations (Essential/Premium/Dedicated), TiUP deployment/upgrade procedures, multi-node behavior, backup/restore, disaster recovery, and ticloud CLI. Mark unsupported runtime steps `NOT-COVERED`; continue independent document/source checks within the requested scope.
- **First local SQL run**: load [the short walkthrough](ref-tidb.md#first-local-sql-run) only for initial setup. **Scheduled or batch regression**: load [the run contract and JSON report format](ref-scheduled-regression.md) only when needed.

## Architecture principle (non-negotiable)

**The documentation agent is the single reasoning and verdict layer.** Tools expose evidence and execute actions; they do not independently adapt the test or decide its verdict.

- **Self-healing is permitted; silent self-healing is not.** You may retry with a different selector or endpoint to keep the task track alive, but every adaptation MUST be logged as a candidate drift finding.
- **API/CLI state is the fact layer; UI is the narrative layer.** Assert resource state via API or SQL. Use UI observation only for what the doc promises a user will see.
- **Full observations go to disk; only deltas enter context.** Never let raw dumps flood the conversation.

## The test protocol (run per claim or document step)

1. **PREDICT** — extract the documented claim or expected result: page name, button labels, default values, expected output or outcome text. Write it down and select the required verification methods before collecting evidence.
2. **OBSERVE** — collect the relevant document context, source definitions and validation paths, or environment state for the selected methods. Preserve the documented expectation when the evidence differs.
3. **COMPARE** — check the prediction against the observation explicitly, line by line. Never eyeball.
4. **ACT** — for runtime checks, perform the action like a user would within the authorized scope. On failure, see the self-healing rule above. Document and source checks do not require an environment mutation.
5. **VERIFY** — evaluate the collected evidence against the claim. For runtime checks, verify the actual output or resulting state; poll when needed and avoid fixed sleeps except as a last resort.
6. **RECORD** — save evidence to file and report the result, verification methods completed, and remaining gaps separately. Only the delta (vs prediction or baseline) enters context; screenshots serve as evidence at checkpoints and anomalies.

## Select verification methods per claim

Split the document into verifiable claims and steps. Choose one or more methods for each item automatically; the user does not need to specify the methods or repeat the standard workflow. Do not assign a single method to an entire page when its claims need different evidence.

| Method | Use for | Evidence and limits |
|---|---|---|
| `DOC-CHECK` | Internal contradictions, missing prerequisites, step order, and inconsistencies between prose, tables, and examples | Cite the document locations that support the finding. Model knowledge can suggest checks, but cannot establish product behavior as verified. |
| `SOURCE-CHECK` | Declared defaults, minimum/maximum values, scope, feature flags, and validation conditions | Inspect the target version's definitions and relevant validation/call paths, not just matching constants. Record the repository, commit, and source locations. This verifies implementation, not deployment or runtime behavior. |
| `RUNTIME-CHECK` | SQL/API input and output, boundary and error behavior, permissions, configuration taking effect, and console workflows | Record inputs, outputs, relevant state, and environment version/configuration. Conclusions apply to the tested environment. |

When an item requires `SOURCE-CHECK`, load [Source repository selection](ref-source-code.md) to map its document topic or asserted behavior to a primary repository and any necessary follow-up sources, then resolve the local/remote source and revision. Do not load that reference for document-only or runtime-only checks.

- Use document evidence to resolve internal consistency questions directly. Prefer source checks for implementation declarations; require runtime evidence for claims about execution, environmental effects, and user-visible behavior. Combine methods where they answer different parts of a claim, without requiring all three for every item.
- Match source code to the document's target version and, for runtime comparisons, record the actual instance version. Do not silently substitute the latest development code for release documentation. When explicitly checking upcoming changes against newer code, label them as pending changes rather than errors in the published version. For TiDB Cloud, distinguish the inspected source revision from the deployed service when their correspondence is unknown.
- Turn source findings into focused runtime assertions when an appropriate environment is available. For a system variable, check the documented default, range, scope, and validation logic in source, then test relevant boundary/invalid inputs and effects of changes in the instance. Preserve source-versus-runtime distinctions in the report.
- If source and runtime evidence conflict, investigate version, deployment, configuration, feature flags, and the relevant execution path. Keep an unresolved conflict explicit rather than selecting one source as automatically authoritative or issuing `PASS`.
- If a required method is unavailable or excluded by scope, complete independent checks and record the missing check as `ENV-BLOCKED` or `NOT-COVERED`, as appropriate. Source-only verification must say that runtime behavior was not tested; it cannot establish an overall E2E pass.

## Routing: two layers, never bind product to tool

**Layer 1 — target environment.** Determine: TiDB or TiDB Cloud; use an existing environment or validate a create/deploy flow; **version** and scope. Version is a test input: TiDB docs are tested against an instance of the matching version; Cloud docs consider both the release branch and current service behavior. A version mismatch is recorded explicitly — it is never silently filed as a doc error.

**Layer 2 — runtime execution method.** For items requiring `RUNTIME-CHECK`, choose Browser / SQL / REST API / Shell-CLI. One doc may combine several methods; test each part on its own method and merge findings into one report. Load environment prerequisites only for the checks that need them; document/source checks do not require a live connection or console login.

Load the matching reference file only when needed:

| Environment | Reference file | Covers |
|---|---|---|
| TiDB (self-hosted) | `ref-tidb.md` | playground lifecycle, version alignment, environment tiers, phase scope |
| TiDB Cloud | `ref-tidb-cloud.md` | console login/org checks, browser pitfalls, REST API specs |

**Reference docs are not blindly runnable.** System variable references, SQL statement pages, and similar often contain mutually exclusive examples, expected-error examples, and independent scenarios. Partition such pages into test cases with preconditions first; never execute the whole file top to bottom without that partitioning. (`scripts/scan-sql-blocks.py` produces the block inventory to plan this.)

## Verdict taxonomy

Assign each check one result below and record its verification method separately. If methods have different outcomes, retain separate check rows; an unresolved conflict is not a pass.

| Verdict | Meaning |
|---|---|
| `PASS` | Evidence from the recorded method supports the specific claim; this does not imply that other methods were completed |
| `DOC-DISCREPANCY` | Document, matching source, or runtime evidence establishes a documentation inconsistency → candidate doc fix. Source-only discrepancies must record the inspected commit and remain marked as runtime-unverified |
| `PRODUCT-ANOMALY` | Product itself misbehaves regardless of the doc → not a doc bug; report separately |
| `VERSION-MISMATCH` | Environment version/edition differs from what the doc targets → record, do not judge the doc |
| `ENV-BLOCKED` | Test could not run (login expired, quota, network) → retry after fixing; never counts as pass or fail |
| `NOT-COVERED` | Required check excluded by the requested scope or not testable with currently supported flows → record the reason and dependent checks left uncovered |

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

Resolve and record the document path/revision, target product/version, environment, mutation and creation scope, required verification methods, and output directory from the request and existing context. Do not turn these into a mandatory questionnaire. Unattended runs use the explicit contract in [Scheduled regression](ref-scheduled-regression.md).

## Report format

Write every test report in **English** under `.tmp/test-reports/<run-id>/` (or the requested output directory), using a unique run ID and a document-path-derived filename to avoid collisions. Scheduled runs also require the JSON sidecar defined in [Scheduled regression](ref-scheduled-regression.md); for interactive runs it is optional. The agent assembles reports from evidence; the bundled harness does not emit this sidecar automatically. Include:

- Header: document path and commit, target product/version, inspected source repository and commit when used, runtime environment/instance when used, scope, and date.
- Per-claim/step table: document location, expected claim/result, verification method (`DOC-CHECK`, `SOURCE-CHECK`, or `RUNTIME-CHECK`), evidence with source locations or runtime artifact links, result from the taxonomy, and remaining verification gaps.
- Overall result and coverage: distinguish document/source verification from runtime execution. For example, "Range verified in source; out-of-range input behavior not tested." Do not report an overall E2E pass when required runtime checks are blocked, excluded, or unexecuted.
- Issues ranked by severity with human-verdict flags, unresolved evidence conflicts, resource IDs created and cleaned up, setting restoration results, infrastructure learnings, and cleanup confirmation where applicable.

## Scripts

- `scripts/run-sql-test.py` — SQL-doc harness: extract `sql` blocks, execute them in document order over ONE shared connection (session state carries), compare with documented expected output (exact / weak / smoke). Works for local playground and TiDB Cloud Starter alike. Mislabeled output blocks (result tables tagged as sql) are auto-detected.
- `scripts/snapdiff.py` — normalize two a11y snapshots and diff (strip refs, mask high-entropy values only, drop proven-volatile lines only; content-only compare + order fallback).
- `scripts/observe_page.py` — filtered AX-tree observation for Browser Use CLI; output format is snapdiff-compatible, includes form values and control states.
- `scripts/api_orchestrator.py` — TiDB Cloud serverless v1beta1 API helper: wait for ACTIVE, delete by clusterId, run SQL; `--dry-run` covers all side effects.
- `scripts/lib/markdown_sql.py` — shared Markdown/SQL parser (fences, block classification, transcripts, expected tables, expected errors, statement typing). Scanner and runner BOTH use it — they can never disagree about what a block is.
- `tests/` — unit/golden tests for the harness itself (`python3 -m unittest discover -s tests` from the skill directory). Harness invariants: never emit a stronger result than evidence supports; never normalize away a documentation-relevant difference.
- `scripts/scan-sql-blocks.py` — repo inventory: count SQL blocks per doc, classify statement types, flag environment dependencies, score automatability. Single-file mode gives per-block inventory (index, lines, kind) for test-case partitioning.

The SQL harness validates prepared, sequential SQL cases; it cannot establish multi-node behavior, performance claims, or external workflow correctness. Its nondeterminism detection is limited: use explicit weak assertions for variable output, and report their strength. A smoke pass means execution succeeded, not that documented results matched; neither smoke nor `SELECT` syntax guarantees a read-only operation. The harness has no dry-run or expected-error assertion mode: inspect cases before execution and verify documented errors separately.
