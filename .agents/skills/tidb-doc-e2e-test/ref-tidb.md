# TiDB track (self-hosted docs)

Load this file when the document under test targets TiDB (not TiDB Cloud). Typical targets: `sql-statements/`, `functions-and-operators/`, `develop/`, `information-schema/`, root-level feature docs, quickstarts.

## Environment

- **Existing environment first**: reuse the designated compatible test cluster. If a disposable local environment is authorized, use `tiup playground <pinned-version> --db 1 --kv 1 --pd 1 --tiflash 0 --without-monitor`; inspect its actual endpoint before connecting. Do not recreate a user-provided cluster.
- **Version pinning is mandatory**: the doc branch tracks a TiDB version; pin playground to it (`tiup playground v8.5.7`). A behavior difference between the doc's version and the playground's version is `VERSION-MISMATCH`, not `DOC-DISCREPANCY`.
- **Extended playground flags** unlock more docs: `--tiflash 1` (HTAP/MPP docs), `--ticdc 1` + a second playground as downstream, `--tiproxy 1`, `--kv 3` (multi-store label simulation).

## Environment tiers (what needs what)

| Tier | Environment | Unlocks |
|---|---|---|
| E0 | playground (+ flags) | SQL statements, functions, features, TiFlash/MPP, basic TiCDC/TiProxy |
| E1 | playground + local Docker (MinIO, Kafka) | BR to S3, TiCDC→Kafka, Lightning/Dumpling, sync-diff-inspector |
| E2 | + upstream MySQL container(s) | DM docs, MySQL→TiDB migration guides |
| E3 | one Linux VM, loopback SSH | tiup cluster deploy/scale/upgrade, TLS/encryption-at-rest, config references |
| E4 | 3–5 Linux VMs | geo-redundancy topologies, full placement rules, OS/kernel tuning |
| E5 | local Kubernetes (kind) | TiDB Operator docs |
| E6 | E3/E4 + load/chaos tools | troubleshoot-*, benchmark steps (numbers never assertable) |

Phase-1 scope is E0 SQL examples. Higher tiers are planning information, not implemented test flows; provisioning a tier alone does not enable the unsupported procedures listed in SKILL.md.

## First local SQL run

Load this walkthrough only for a first local run. It uses one SQL page and no Cloud account. Prerequisites: TiUP, MySQL client, Python 3, a local `release-8.5` docs ref, and permission to start a disposable playground. This example pairs that doc branch with TiDB v8.5.7; it is not a claim that this is the latest patch or that every page on the branch targets that patch. Verify version fit and review the selected examples before execution.

From the docs repository, start the playground in terminal A and wait for its ready message. Ensure the chosen endpoint belongs to this new process; do not connect to another local instance accidentally.

```bash
tiup playground v8.5.7 --db 1 --kv 1 --pd 1 --tiflash 0 --without-monitor
```

In terminal B, also at the docs repository root, export a committed page without changing branches, inventory its blocks, and verify the endpoint/version. The commands assume the reported port is 4000; use the actual port otherwise. Stop on a failed command.

```bash
DOC_E2E_RUN=$(mktemp -d "${TMPDIR:-/tmp}/doc-e2e-first.XXXXXX")
git rev-parse release-8.5 > "$DOC_E2E_RUN/doc-commit.txt"
git show "$(cat "$DOC_E2E_RUN/doc-commit.txt"):functions-and-operators/bit-functions-and-operators.md" > "$DOC_E2E_RUN/bit-functions.md"
python3 .agents/skills/tidb-doc-e2e-test/scripts/scan-sql-blocks.py "$DOC_E2E_RUN/bit-functions.md"
mysql -h 127.0.0.1 -P 4000 -u root -e 'SELECT VERSION();'
```

Review the exported page and inventory for independent cases, required setup, and expected errors. This page's SQL examples can be checked without creating tables. Then run:

```bash
python3 .agents/skills/tidb-doc-e2e-test/scripts/run-sql-test.py "$DOC_E2E_RUN/bit-functions.md" --host 127.0.0.1 --port 4000 --user root > "$DOC_E2E_RUN/sql-results.txt" 2>&1
cat "$DOC_E2E_RUN/sql-results.txt"
```

Keep the exit status and raw output as evidence and write the English report using SKILL.md. These commands test executable examples, not every prose claim. In terminal A, press Control+C and verify the playground exits even if testing failed; retain the evidence directory. An untagged playground cleans up its cluster data on normal shutdown, as described in the [TiUP playground reference](https://docs.pingcap.com/tidb/stable/tiup-playground/).

## Existing vs created environment

- **Playground created for the test**: full cleanup — just stop it.
- **User-provided existing cluster**: treat as production-adjacent. Only read/execute what the doc requires; any database/table/user created must be dropped; any `SET GLOBAL` or config change must be reverted and the original value recorded in the report. Never drop pre-existing objects.

## Reference-doc partitioning

Before running a reference page (`system-variables.md`, `sql-statements/*`, function references):

1. Run `scripts/scan-sql-blocks.py`-style inventory on the file.
2. Partition into test cases: setup (shared DDL/data), independent examples, mutually exclusive examples (e.g. conflicting `SET` values), expected-error examples (assert the documented error code/message — a *missing* error is the failure).
3. Execute per case, not the whole file linearly.

The harness accepts a Markdown file, not a case-selection flag. For partitioned pages, prepare a temporary Markdown file per case with the required setup and expected output, preserving a mapping to original lines. Expected-error examples and nondeterministic results beyond the harness's recognized patterns require separate assertions; record the actual strength (exact, weak, or smoke).

## Known pitfalls (TiDB track)

- Docs on `master` track the development version — discrepancies against a pinned release need a human verdict before any doc edit.
- Binary output in docs assumes `--binary-as-hex` on the mysql client.
- EXPLAIN outputs contain cost estimates, timestamps, and region IDs — weak assertions only.
- `sql`-tagged blocks may contain result tables or `mysql>` transcripts; `run-sql-test.py` auto-detects these.
