# TiDB Cloud track

Load this file when the document under test targets TiDB Cloud: console UI guides, quickstarts, SQL against Starter/Essential, or REST API specs from the idl repo.

## Environment setup (machine-specific — verify before use)

**Detect what is actually available on this machine instead of assuming the paths below exist** — they are examples from a known-working setup:

- **Playwright MCP**: expected in the agent CLI's MCP config with a persistent browser profile. Verify by listing available `mcp__playwright__*` tools.
- **Chrome DevTools MCP**: expected whitelisted to console/network tools (`list_console_messages`, `get_network_request`, ...). Verify by listing `mcp__chrome-devtools__*` tools.
- **Browser Use CLI**: check for a venv (e.g. `.tmp/venv-browseruse`); if missing: `python3 -m venv .tmp/venv-browseruse && .tmp/venv-browseruse/bin/pip install browser-use`. It needs a shared Chrome because Playwright MCP cannot hold the same profile simultaneously:
  ```bash
  # NOTE: do NOT quote the glob — let the shell expand it
  CHROME=$(ls -d "$HOME"/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/*.app 2>/dev/null | sort | tail -1)
  "$CHROME/Contents/MacOS/"* --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.kimi-code/playwright-profile" --no-first-run &
  export BU_CDP_URL=http://127.0.0.1:9222
  ```
- **API keys** (assertion/cleanup): `TidbCloudPublicKey` / `TidbCloudPrivateKey` env vars. Never commit them.
- **REST API specs**: idl repo branches `release/v1beta1` / `release/v1beta2`, `swagger/*.swagger.json`. Resolve the local clone path with the user instead of assuming one. Spec-vs-live method: resolve an endpoint from the spec, call the live API (HTTP Basic with the key pair), compare the response against the spec schema (status code, required fields, field types). A mismatch is a candidate drift finding.

## Pre-flight checklist (before any Cloud test)

1. **Session health**: navigate to `https://tidbcloud.com/tidbs`. If redirected to `auth.tidbcloud.com`, stop and ask the user to log in (auth0 session expires in hours). Never automate credentials.
2. **Correct org**: verify the org name on the My TiDB page matches the intended test org.
3. **Cost safety**: Starter instances only, spending limit $0.
4. **Baseline availability** (regression mode): no baseline → this run is a first pass; produce baselines as a byproduct (subject to the first-pass rule in SKILL.md).

## Existing vs created Cloud resources

- **Instance created for the test**: name it `docs-e2e-*`, record its `clusterId`, delete it by ID at the end (see `scripts/api_orchestrator.py`). Console-delete requires typing `org-name/instance-name` — handle non-ASCII org names.
- **Pre-existing instance the user offers** (e.g. "Cluster0 is fine, don't delete it"): never delete or disable anything permanently. Reversible probes (disable→re-enable a public endpoint) need explicit user awareness. Record every state change and restore it; note residual changes (e.g. a generated password) in the report.

## Known pitfalls (Cloud console — learned from live testing, do not rediscover)

- **CodeMirror editors** (SQL Editor): never `type` SQL character-by-character — auto-completion corrupts backticks/parens. Focus `.cm-content` and use `keyboard.insertText`.
- **Mantine UI** (the whole console): `text=` selectors collide constantly (10 matches for "Starter"). Snapshot first, act on refs; refs go stale after every re-render.
- **React wipes injected DOM**: inject synthetic fixtures at `document.body` level, never inside a React-managed tree.
- **Indentation is not a diff key**: diff snapshots on content only (role + name), handled by `scripts/snapdiff.py`.
- **Set-based diffs miss relocation**: `snapdiff.py` has an order-aware fallback; keep it.
- **Run executes only the statement at the cursor**: in SQL Editor with multiple statements, select all (⌘A) before Run, or use ⇧⌘Enter.
- **Prefer JS `element.click()` over CDP coordinate clicks in batch mode**: AX box-model coordinates can mismatch the headed viewport, and synthetic mouse events may not trigger React handlers.
- **`innerText` omits input values**: combobox defaults (e.g. `Public`, `main`, `macOS`) are invisible to `innerText` probes — dump `input.value` separately.
- **My TiDB instance names are table cells, not links**: locate the `<p>`/`<td>` by text and click it.
- **New-account behaviors vary by account vintage**: e.g. the auto-created default instance name has differed between orgs. Verify against a fresh sign-up before filing a doc fix for onboarding claims.
