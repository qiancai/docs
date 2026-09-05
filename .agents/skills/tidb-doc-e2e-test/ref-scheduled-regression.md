# Scheduled regression

Load for unattended or batch regression, or when a machine-readable report is requested. This file defines a workflow contract; it does not create a schedule or implement a runner. Reuse the chosen scheduler and the same version-controlled skill.

## Suitable jobs

- Start with a fixed document list: source checks against explicit revision policies, prepared SQL cases, read-only API contract checks, or inventory refreshes. Inventory counts are planning data, not correctness results.
- Keep exact assertions where deterministic expected results exist. Use smoke only where no stronger assertion is available; smoke describes assertion strength, not permission to mutate.
- Browser regression is conditional on a previously exercised flow, available browser adapter, valid session, and saved failure evidence. Interactive login/MFA or unstable prerequisite state produces `ENV-BLOCKED`; do not attempt account signup or credential recovery unattended.
- Paid Cloud flows and unsupported procedures remain excluded. Creation/deletion of disposable local or Starter test resources requires a previously established plan, specific authorization, and verified cleanup. Otherwise use existing targets and mark excluded operations `NOT-COVERED`.

## Fixed input contract

Resolve this contract during setup, reusing known context and authorization. Store it with the scheduled job in a readable file or scheduler configuration; the fields below are not CLI flags for the bundled scripts. At each run, record resolved commits and actual environment details. Missing execution-critical input blocks affected checks; do not wait for a reply inside an unattended run.

| Input | Required meaning |
|---|---|
| `workspace`, `docs`, `doc_ref` | Repository location, explicit repository-relative document paths, and a pinned commit or named branch/tag policy. Resolve moving refs to a commit once per run. |
| `product`, `target_version`, `source_refs` | TiDB or TiDB Cloud Starter, intended release/version, and source revision policy when source checks are required. Record unknown deployed Cloud revisions explicitly. |
| `environment` | Existing target identity and connection/profile references, or an authorized disposable-environment recipe. Reference credentials by configured secret/environment names; never put secret values in the job or report. |
| `mutation_scope`, `allow_create` | Default unattended scope is read-only with creation disabled unless previously authorized otherwise. Enumerate allowed writes, target boundaries, restoration, and cleanup; creation permission does not authorize deleting pre-existing resources. |
| `required_methods` | Methods that must complete for the job's intended coverage, including `RUNTIME-CHECK` when runtime is required. The agent still selects evidence per claim; unavailable required methods remain explicit gaps. |
| `output_dir`, `timeout`, `concurrency` | Report root, bounded execution time, and overlap policy. Do not run concurrent mutations against the same instance/schema/profile. |

## Execution and failure handling

1. Read the contract, resolve revisions, and detect only the capabilities required for selected checks. Recheck document/case changes against the allowed operations; a previously read-only file may acquire writes. Do not bypass the contract because SQL is labeled smoke or starts with `SELECT`.
2. Before the first unattended mutating run, or when its targets/actions change, inspect the exact plan and cleanup. Use `api_orchestrator.py --dry-run` when that helper performs the action; it validates intended calls, not authentication or live behavior. `run-sql-test.py` has no dry-run: use inventory plus case inspection. Repeat unchanged plans within their existing authorization without requesting approval each run.
3. Execute prepared cases and save outputs, exit codes, and failures. Do not blindly rerun mutations after a timeout or uncertain response; inspect resulting state first. Retain supported checks when another method is blocked.
4. Restore changed settings and clean up only this run's resources on success or failure. If cleanup fails, retain resource IDs and mark it failed. Apply the main verdict taxonomy; a tool/parser failure is a blocked check, not a product or documentation defect. Unresolved evidence conflicts cannot pass.
5. Write Markdown and JSON even for blocked/partial runs. Keep baselines unchanged unless the main baseline acceptance rules are satisfied. Notify only on meaningful new/changed findings, failures, cleanup problems, or required intervention unless periodic summaries were requested.

## JSON sidecar

For scheduled runs, the agent writes one `.md`/`.json` pair per document in `<output_dir>/<run-id>/`. Use a unique run ID and a filename derived from the full document path. Interactive runs need JSON only when requested. This is agent-assembled output, not a format currently emitted by the SQL harness.

Use `schema_version: 1`. Example of a blocked runtime check (replace illustrative values with observed data):

```json
{
  "schema_version": 1,
  "run_id": "20260905T120000Z-01",
  "skill_commit": "resolved-skill-commit",
  "doc_path": "functions-and-operators/bit-functions-and-operators.md",
  "doc_commit": "resolved-doc-commit",
  "product": "tidb",
  "target_version": "v8.5.7",
  "environment": {"id": "local-test", "actual_version": null},
  "source_refs": [],
  "methods_run": [],
  "verdict_counts": {"ENV-BLOCKED": 1},
  "checks": [{"id": "sql-1", "doc_line": 30, "method": "RUNTIME-CHECK", "assertion": "exact", "verdict": "ENV-BLOCKED", "evidence": ["connection.log"], "reason": "Connection failed; SQL not executed"}],
  "blocked_reasons": ["Connection failed"],
  "created_resource_ids": [],
  "cleanup": {"status": "not-needed", "remaining_resource_ids": [], "reason": null},
  "coverage_complete": false
}
```

`methods_run` contains methods actually executed, not merely planned. `checks` includes blocked/excluded checks and uses the main verdict taxonomy; `assertion` is `exact`, `weak`, `smoke`, or null when inapplicable. `verdict_counts` counts check rows, with absent verdicts meaning zero. Record source references as repository/commit pairs. `cleanup.status` is `ok`, `failed`, `unknown`, or `not-needed`; interruption without verification is `unknown`. `coverage_complete` must be false for required gaps, unresolved conflicts, or failed/unknown cleanup. It means coverage, not correctness: completed checks may still find discrepancies.

Before delivery, parse the JSON with a standard JSON parser and reconcile counts, methods, coverage, and cleanup with the Markdown report and raw evidence. Never convert an empty result set into a successful run. Retain raw harness assertion strengths instead of promoting smoke/weak results to exact matches.
