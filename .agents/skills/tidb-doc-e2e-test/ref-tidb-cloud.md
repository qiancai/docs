# TiDB Cloud track

Load this file for TiDB Cloud Starter runtime checks: console guides, quickstarts, SQL, or API specs. Essential, Premium, and Dedicated are outside the current runtime scope.

## Preflight: capability detection

Check capabilities only for the selected execution method. A working SQL/API connection does not require a browser, and browser tests do not require every tool listed here.

- **Browser adapter**: inspect available tools and their documentation; reuse a working browser session through the agent's native browser tools, Playwright MCP, or a configured CDP adapter. Do not assume tool names, injected helpers, or a Browser Use CLI interface exist. Use `observe_page.py` only with a runtime that supplies its helpers. If no compatible adapter exists, report `ENV-BLOCKED` for browser checks.
- **Browser executable/profile**: when launching is necessary, detect OS and architecture (`uname -s`, `uname -m`) and use the selected adapter's executable discovery or an explicitly configured path. On macOS, use the configured application or adapter-managed browser; on Linux, inspect `command -v chromium`, `command -v chromium-browser`, or `command -v google-chrome`, or use the adapter-managed binary. These are discovery options, not mandatory installs or fixed cache paths.
- **Display and session**: on Linux/EC2, use headless mode when supported, or a configured display for headed mode. Provide a human login/recovery path for interactive authentication. A persistent profile does not guarantee a valid login. Isolate concurrent profiles and never attach two controllers to the same profile simultaneously; keep any CDP listener local or behind an authenticated tunnel.
- **Diagnostics**: use console/network inspection from the available adapter; Chrome DevTools MCP is optional. Save snapshots and screenshots at failures so remote runs remain reviewable.
- **API keys** (assertion/cleanup): `TidbCloudPublicKey` / `TidbCloudPrivateKey` env vars. Never commit them.
- **REST API specs**: resolve the idl clone from existing context and verify the target API revision. Select the spec's host, path, and authentication scheme; do not assume all API versions use the same scheme. Compare live status, required fields, and types against the spec. A mismatch is a candidate finding, not automatically a documentation error.

## Pre-flight checklist (per execution method — check only what the method needs)

- **Browser flows**: navigate to `https://tidbcloud.com/tidbs`. If redirected to `auth.tidbcloud.com`, stop and ask the user to log in (auth0 session expires in hours; never automate credentials). Verify the org name on the My TiDB page matches the intended test org.
- **SQL flows** (run-sql-test.py against a Starter instance): verify DB connectivity first — `mysql --ssl-mode=REQUIRED -h <host> -P 4000 -u '<prefix>.root' -e 'SELECT 1'` with `MYSQL_PWD` set. No console login required.
- **REST API flows**: verify the API key pair works — one cheap authenticated call (e.g. `GET /v1beta1/clusters` with pageSize=1) before starting. No console login required.
- **Cost safety (all methods)**: Starter instances only, spending limit $0.
- **Baseline availability** (regression mode): no baseline → this run is a first pass; produce baselines as a byproduct (subject to the first-pass rule in SKILL.md).

## Existing vs created Cloud resources

- **Instance created for the test**: name it `docs-e2e-*`, record its `clusterId`, delete it by ID at the end (see `scripts/api_orchestrator.py`). Console-delete requires typing `org-name/instance-name` — handle non-ASCII org names.
- **Pre-existing instance the user offers** (e.g. "Cluster0 is fine, don't delete it"): never delete or disable anything permanently. Reversible probes (disable→re-enable a public endpoint) need explicit user awareness. Record every state change and restore it; note residual changes (e.g. a generated password) in the report.

## Known pitfalls (Cloud console — learned from live testing, do not rediscover)

- **CodeMirror editors** (SQL Editor): never `type` SQL character-by-character — auto-completion corrupts backticks/parens. Focus `.cm-content` and use `keyboard.insertText`.
- **Interaction hierarchy (user truthfulness)**: a doc test asks "can a user do this?", so clicks must be user-equivalent. Order: (1) accessible/native locator click, (2) DOM locator click, (3) scroll into view + retry, (4) JS `element.click()` as diagnostic fallback only. JS clicks bypass overlays, hit-targets, and visibility — if only the JS click works, record "user interaction failed; JS invocation confirms the handler works" as a potential `PRODUCT-ANOMALY`, never a `PASS`.
- **Mantine UI** (the whole console): `text=` selectors collide constantly (10 matches for "Starter"). Snapshot first, act on refs; refs go stale after every re-render.
- **React wipes injected DOM**: inject synthetic fixtures at `document.body` level, never inside a React-managed tree.
- **Indentation is not a diff key**: diff snapshots on content only (role + name), handled by `scripts/snapdiff.py`.
- **Set-based diffs miss relocation**: `snapdiff.py` has an order-aware fallback; keep it.
- **Run executes only the statement at the cursor**: in SQL Editor with multiple statements, select all in the editor (Command+A on macOS, Control+A on Linux/Windows) before Run; verify any alternative shortcut in the current UI.
- **`innerText` omits input values**: combobox defaults (e.g. `Public`, `main`, `macOS`) are invisible to `innerText` probes — dump `input.value` separately.
- **My TiDB instance names are table cells, not links**: locate the `<p>`/`<td>` by text and click it.
- **New-account behaviors vary by account vintage**: an existing account cannot validate fresh-signup claims. Signup testing is outside current scope; record those claims as `NOT-COVERED` rather than creating an account.
