---
name: tidb-cloud-e2e
description: End-to-end test TiDB Cloud documentation against the live console using a human-like test protocol — predict, observe, compare, act, verify, record — with Playwright MCP for exploration, CDP/Browser Use CLI for batch observation, semantic snapshot diff for drift detection, and Chrome DevTools MCP for failure diagnosis. Use when validating docs in tidb-cloud/ (console UI guides, quickstarts) or setting up nightly doc drift detection.
---

# TiDB Cloud E2E Documentation Testing

Use this skill when the task is to test a TiDB Cloud documentation page against the live TiDB Cloud console, detect documentation drift, or set up regression runs for console UI docs.

## Architecture principle (non-negotiable)

**The documentation agent is the single reasoning and verdict layer.** The browser layer only exposes page state and executes actions — it must never independently decide how to adapt to UI changes.

```
Documentation Agent (SINGLE REASONER)
    │ decide / compare / judge
    ├── Browser control: Playwright MCP / Browser Use CLI (CDP)
    ├── Diagnostics: Chrome DevTools MCP (console/network only)
    └── Ground truth: TiDB Cloud API + SQL client
```

A browser agent that "helpfully" clicks a renamed button and reports PASS is a missed finding, not robustness. Therefore:

- **Self-healing is permitted; silent self-healing is not.** You may retry with a different selector to keep the task track alive, but every adaptation MUST be logged as a candidate drift finding.
- **API is the fact layer; UI is the narrative layer.** Assert resource state (instance exists, Active) via API. Use UI observation only to verify what the doc promises a user will see — button names, defaults, texts, flows. That narrative fidelity is the actual test target.
- **Full observations go to disk; only deltas enter context.** Never let raw page dumps flood the conversation.

## The test protocol (run per document step)

Mimic how a human tests documentation. For each step of the doc:

1. **PREDICT** — extract from the doc step what the user should see: page name, button labels, default values, expected outcome text. Write it down before observing.
2. **OBSERVE** — observe each page state exactly once, with the cheapest tool that carries full state (see tool matrix).
3. **COMPARE** — check the predicted element list against the observation explicitly, line by line. Never eyeball.
4. **ACT** — perform the action like a user would (clicks, keyboard shortcuts, typing). On selector failure, see self-healing rule above.
5. **VERIFY** — poll for the resulting state change (e.g. `browser_wait_for` text, or API status). Do not use fixed sleeps except as a last resort.
6. **RECORD** — save the full snapshot to a file; put only the delta (vs prediction or vs baseline) into context. Take screenshots as evidence only at checkpoints and anomalies.

## Tool selection matrix

| Moment | Tool | Why |
|---|---|---|
| Exploration: need to locate and click elements | Playwright MCP snapshot | ref-based actions are most precise |
| Batch observation for comparison | Browser Use CLI / raw CDP with `scripts/observe_page.py` | ~5 KB vs ~12 KB per page, filtered in-process |
| Drift check in regression runs | `scripts/snapdiff.py` against baseline | ~100 tokens/page; 6/6 mutation detection validated |
| Visual anomalies / evidence | MCP screenshot | only at checkpoints, never by default |
| Failure diagnosis | Chrome DevTools MCP (`list_console_messages`, `list_network_requests`) | distinguishes selector failure from API 403 |
| Resource state assertion / cleanup | `scripts/api_orchestrator.py` (TiDB Cloud API) | UI can lie; API cannot |

## Environment setup

- **Playwright MCP**: configured in `~/.kimi-code/mcp.json` with persistent profile `~/.kimi-code/playwright-profile` (login state survives across sessions).
- **Chrome DevTools MCP**: same file, whitelisted to console/network tools.
- **Browser Use CLI**: venv at `.tmp/venv-browseruse`. Needs a shared Chrome because Playwright MCP cannot hold the same profile simultaneously:
  ```bash
  "$HOME/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.kimi-code/playwright-profile" --no-first-run &
  export BU_CDP_URL=http://127.0.0.1:9222
  ```
- **API keys** (assertion/cleanup): `TidbCloudPublicKey` / `TidbCloudPrivateKey` env vars + project ID. Never commit them.

## Pre-flight checklist (before any test)

1. **Session health**: navigate to `https://tidbcloud.com/tidbs`. If redirected to `auth.tidbcloud.com`, stop and ask the user to log in (auth0 session expires in hours).
2. **Correct org**: verify the org name on the My TiDB page matches the intended test org.
3. **Cost safety**: Starter instances only, spending limit $0. Every created instance MUST be deleted in a `try/finally`-style cleanup, named `docs-w2-pilot-*` or `docs-e2e-*` for identifiability.
4. **Baseline availability** (regression mode): does a baseline snapshot exist for this page? If not, this run is a first pass — produce baselines as a byproduct.

## Known pitfalls (learned from live testing — do not rediscover)

- **CodeMirror editors** (SQL Editor): never `type` SQL character-by-character — auto-completion corrupts backticks/parens. Focus the `.cm-content` element and use `keyboard.insertText`.
- **Mantine UI** (the whole console): `text=` selectors collide constantly (10 matches for "Starter"). Always `browser_snapshot` first and act on refs; refs go stale after every re-render and must be re-acquired.
- **React wipes injected DOM**: synthetic mutations/test fixtures injected inside a React-managed tree disappear on re-render. Inject at `document.body` level.
- **Indentation is not a diff key**: injected landmarks change tree nesting and make identical content look rewritten. Diff on content only (role + name).
- **Set-based diffs miss relocation**: use the order-aware fallback in `snapdiff.py` when content sets are equal but sequences differ.
- **Run executes only the statement at the cursor**: in SQL Editor with multiple statements, select all (⌘A) before clicking Run, or use ⇧⌘Enter.
- **Delete confirmations require typing `org-name/instance-name`**: handle non-ASCII org names.
- **Auth sessions expire in hours**: pre-flight check catches this; the fix is always a human re-login, never credential automation.
- **Prefer JS `element.click()` over CDP coordinate clicks in batch mode**: AX box-model coordinates can mismatch the headed viewport, and synthetic CDP mouse events may not trigger React handlers. Coordinate clicks are a fallback, not a default.
- **`innerText` omits input values**: combobox/dropdown defaults (e.g. `Public`, `main`, `macOS`) are invisible to `innerText` probes. Dump `input.value`/`combobox` values separately when verifying form defaults.
- **My TiDB instance names are table cells, not links**: locate the `<p>`/`<td>` by text and click it; there is no `<a>` to match.

## Report format

Write every test report in **English** to `.tmp/test-reports/<date>-<doc-name>.md` with: header (doc, environment, instance, date), verdict, per-step table (doc step / actual result / PASS-FAIL-diff), issues found ranked by severity with human-verdict flags, infrastructure learnings, and cleanup confirmation.

## Scripts

- `scripts/observe_page.py` — filtered AX-tree observation for Browser Use CLI (`browser-use < observe_page.py`). Prints role+name lines only.
- `scripts/snapdiff.py` — normalize two a11y snapshots and diff (3 rules: strip refs/attrs, mask numbers/times, drop volatile lines; content-only compare + order fallback).
- `scripts/api_orchestrator.py` — TiDB Cloud API helper: wait for cluster AVAILABLE, delete by name, run SQL assertions. `--dry-run` supported.
