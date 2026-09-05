# TiDB track (self-hosted docs)

Load this file when the document under test targets TiDB (not TiDB Cloud). Typical targets: `sql-statements/`, `functions-and-operators/`, `develop/`, `information-schema/`, root-level feature docs, quickstarts.

## Environment

- **Default environment**: `tiup playground <pinned-version> --db 1 --kv 1 --pd 1 --without-monitor`, MySQL client on `127.0.0.1:4000`. Disposable — recreate per session, no cleanup guilt.
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

Phase-1 scope is E0 SQL examples. Anything above E0: mark `NOT-COVERED` unless the user has explicitly set up that tier.

## Existing vs created environment

- **Playground created for the test**: full cleanup — just stop it.
- **User-provided existing cluster**: treat as production-adjacent. Only read/execute what the doc requires; any database/table/user created must be dropped; any `SET GLOBAL` or config change must be reverted and the original value recorded in the report. Never drop pre-existing objects.

## Reference-doc partitioning

Before running a reference page (`system-variables.md`, `sql-statements/*`, function references):

1. Run `scripts/scan-sql-blocks.py`-style inventory on the file.
2. Partition into test cases: setup (shared DDL/data), independent examples, mutually exclusive examples (e.g. conflicting `SET` values), expected-error examples (assert the documented error code/message — a *missing* error is the failure).
3. Execute per case, not the whole file linearly.

## Known pitfalls (TiDB track)

- Docs on `master` track the development version — discrepancies against a pinned release need a human verdict before any doc edit.
- Binary output in docs assumes `--binary-as-hex` on the mysql client.
- EXPLAIN outputs contain cost estimates, timestamps, and region IDs — weak assertions only.
- `sql`-tagged blocks may contain result tables or `mysql>` transcripts; `run-sql-test.py` auto-detects these.
