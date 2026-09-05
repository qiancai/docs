# Source repository selection

Load this reference only when a claim or step requires `SOURCE-CHECK`. Use the mappings as starting points for locating the implementation; they do not establish product behavior or expand the supported runtime test scope.

## Resolve the repository and revision

1. Prefer the repository, local path, and revision specified by the user or established in the current session. Reuse that context without asking for it again.
2. Look for an existing clone in the workspace or known sibling repository directories. Verify its identity using Git remotes; do not rely on the directory name alone or hardcode a personal filesystem path. An explicitly selected fork is valid; record its relationship to the upstream repository when relevant.
3. If no suitable clone is available, use the repository links below to inspect the required revision remotely with available read-only tools. Retrieve only the files needed for the claim; do not clone every mapped repository.
4. Resolve the documentation's target version to the relevant source branch, tag, or commit and record the exact commit inspected. The standard mapping is: docs `release-X.Y` branch ↔ product `release-X.Y` branch ↔ `vX.Y.Z` tags — never map a docs release branch to a product's master or latest development branch. Component versions and repository layouts can differ from the TiDB version: follow the target release's dependencies and source history instead of assuming identical tags or today's repository layout. Prefer `git show <revision>:<path>` for committed source without switching the user's checkout. Treat local uncommitted changes as evidence only when the user asks to inspect them, and record that distinction.
5. If the repository, revision, or access cannot be resolved, ask only for the missing information that affects the check. Record the blocked source check and continue independent document or runtime checks. Do not substitute an unrelated repository or the latest development branch.

For development-document checks, pin the inspected development commit. For explicitly requested upcoming-change audits, distinguish newer source behavior from the published document's target version. A Cloud source revision does not prove what is currently deployed.

## Route document topics to product source

Choose the starting repository for each claim by the behavior being asserted, not just keywords or the page title. The primary repository is an entry point, not an exclusive owner. Follow the additional sources only when the claim crosses that component boundary; do not inspect every listed repository for every check.

| Document topic or behavior to verify | Look here first | Follow up when needed |
|---|---|---|
| SQL syntax and compatibility, system variables, optimizer, executor, DDL, and privileges | [tidb](https://github.com/pingcap/tidb) | Follow the execution path into other components when storage or distributed execution affects the claim. |
| SQL transaction semantics, isolation levels, and transaction control statements | [tidb](https://github.com/pingcap/tidb) | [tikv](https://github.com/tikv/tikv) for underlying transaction and locking behavior. Do not route all transaction claims directly to TiKV. |
| Regions, Raft, KV storage, storage engines, and storage-side transaction/consistency mechanisms | [tikv](https://github.com/tikv/tikv) | [pd](https://github.com/tikv/pd) for scheduling decisions; [tidb](https://github.com/pingcap/tidb) for SQL-visible behavior. |
| Placement rules, schedulers, store/member management, cluster metadata, and cluster control | [pd](https://github.com/tikv/pd) | [tikv](https://github.com/tikv/tikv) for storage-side execution; [tidb](https://github.com/pingcap/tidb) when the claim concerns SQL placement-policy syntax or translation into rules. |
| MPP execution, columnar storage, replica synchronization, and HTAP | [tiflash](https://github.com/pingcap/tiflash) | [tidb](https://github.com/pingcap/tidb) for plan generation, optimizer decisions, and SQL controls. Start with TiDB when those are the specific claim being checked. |
| CDC, changefeeds, downstream synchronization, and sink configuration | [ticdc](https://github.com/pingcap/ticdc) | Follow the target release's source history if its implementation lives in another repository. Verify downstream support and component dependencies in that revision. |
| Data Migration (DM): migration tasks, relay log, shard merging, binlog event filters | [tiflow](https://github.com/pingcap/tiflow) (`dm/` directory) | [tidb](https://github.com/pingcap/tidb) when the claim concerns downstream SQL behavior. Note: DM is NOT in the ticdc repository despite the topic similarity. |
| Backup & Restore (BR), TiDB Lightning, Dumpling | [tidb](https://github.com/pingcap/tidb) (`br/`, `lightning/`, `dumpling/` directories) | Storage-side claims follow into [tikv](https://github.com/tikv/tikv). |
| TiProxy: load balancing, traffic replay, connection migration | [tiproxy](https://github.com/pingcap/tiproxy) | [tidb](https://github.com/pingcap/tidb) for backend session/connection semantics. |
| Deployment, upgrades, component installation, playground, and TiUP commands | [tiup](https://github.com/pingcap/tiup) | The deployed component's repository for configuration semantics and runtime behavior. Source lookup does not enable out-of-scope deployment tests. |
| Grafana dashboards, Prometheus rules, monitoring configuration, and alerts | [monitoring](https://github.com/pingcap/monitoring) | The emitting component's repository for metric definitions, units, labels, and emission conditions. For claims about a metric's meaning, start with that component. |
| TiDB Dashboard UI, diagnosis pages, and cluster management pages | [tidb-dashboard](https://github.com/pingcap/tidb-dashboard) | The component providing the backend data when the claim concerns data semantics or service behavior rather than the page itself. |

## Route document and site questions

These repositories provide document context or site implementation evidence. Document text and previews alone do not prove database behavior. Reading the document under test for `DOC-CHECK` does not require loading this mapping.

| Document topic or behavior to verify | Look here first | Follow up when needed |
|---|---|---|
| English document text, version history, and related statements | [docs](https://github.com/pingcap/docs) | The product implementation repository selected above when verifying technical behavior. |
| Chinese document text, version history, and translation context | [docs-cn](https://github.com/pingcap/docs-cn) | [docs](https://github.com/pingcap/docs) for the corresponding English source; product implementation for technical behavior. |
| Documentation site rendering, navigation, and presentation | [website-docs](https://github.com/pingcap/website-docs) | [docs](https://github.com/pingcap/docs) or [docs-cn](https://github.com/pingcap/docs-cn) for the source Markdown and metadata. |
| Document preview generation and preview workflow | [pingcap-docsite-preview](https://github.com/doc-claw-bot/pingcap-docsite-preview), when that preview system is involved | The document source and the rendering implementation actually used by that preview. |

## TiDB Cloud source boundaries

The product mapping above does not identify every Cloud service repository. For Cloud-specific claims, resolve the relevant console, API definition, or backend repository from the task context and available repository metadata; ask for its location only if necessary.

- Console code can establish UI labels and frontend validation for the inspected revision, but does not establish backend enforcement.
- An API specification establishes the declared contract. To verify implementation, follow the backend handler and validation paths when accessible; otherwise report contract verification with backend verification still outstanding.
- Shared TiDB implementation does not by itself establish Cloud availability, defaults, or restrictions. Inspect service-specific configuration or verify the behavior in the target environment.

## Capture source evidence

For each source check, record the document location and claim, repository URL, exact source commit, file and line locations (prefer commit-pinned links), relevant definitions and validation/call paths, and any configuration or version conditions. Distinguish directly observed implementation from inferences. Tests can corroborate the implementation, but neither source nor test code proves that the behavior was exercised in the user's environment.
