---
name: webapp-test-orchestrator
description: End-to-end web app testing. Use when user says "test the app", "run e2e", "smoke test", "regression run", "check the login/onboarding/chat flow", "audit accessibility", "test responsive", or "find bugs in <url>" — even when Playwright is not named. Bootstraps Playwright + axe-core, runs LLM exploration on first run, deterministic replay afterward, emits markdown report + bugs.json + *.spec.ts files with run-diffing.
trigger: /test-app
---

# webapp-test-orchestrator

End-to-end testing orchestrator for web applications. Splits into **first-run exploratory** (LLM-driven via Playwright MCP) and **nth-run deterministic replay** (`npx playwright test`, ~zero LLM tokens). Emits regression specs, normalized bugs.json, markdown + HTML report.

## Project state (auto-injected at skill load)

- Working dir:        !`pwd`
- Tests dir:          !`test -d tests && echo yes || echo no`
- Playwright deps:    !`test -f node_modules/.bin/playwright && echo yes || echo no`
- Config:             !`test -f playwright.config.ts && echo yes || echo no`
- Auth state:         !`test -f playwright/.auth/user.json && echo present || echo missing`
- Listening servers:  !`bash -c 'command -v lsof >/dev/null && lsof -iTCP:3000,5173,8000,8080,8081 -sTCP:LISTEN -P -n 2>/dev/null | tail -n +2 || (command -v ss >/dev/null && ss -tlnp 2>/dev/null | grep -E ":3000|:5173|:8000|:8080|:8081") || echo none'`
- Last run id:        !`bash -c 'r=$(ls -1t reports 2>/dev/null | head -1); echo "${r:-never}"'`
- Last bugs JSON:     !`bash -c 'b=$(ls -t reports/*/bugs.json 2>/dev/null | head -1); echo "${b:-none}"'`
- Isolation verified: !`test -f "${CLAUDE_SKILL_DIR}/.isolation-verified" && echo yes || echo no`
- Test creds file:    !`test -f .env.test && echo yes || echo missing`

## Image budget protection — READ FIRST, MANDATORY

**The problem:** screenshots burn Claude Code's parent-chat **image cap** (~50–100 inline image blocks per session) before they burn its text context. Standalone Playwright MCP usage hits this wall fast. Once hit, the user must `/compact` even at 20% text-context usage.

**The hard rule, enforced by you (not by frontmatter):**

> **NEVER call `Playwright:browser_take_screenshot`, `chrome-devtools:take_screenshot`, or `Read` on `.png/.jpg/.webp` files from the parent skill context. ALWAYS dispatch a Task subagent (general-purpose) to do anything that produces or consumes images. Subagent returns ONLY text — paths, descriptions, verdicts.**

This contract was attempted via `context: fork` frontmatter but Claude Code 2.1.x on Windows does not honor that field, so enforcement is delegated to *you reading these instructions*. Verified empirically 2026-04-28 (sub-agent isolation works; `context: fork` does not parse). See `${CLAUDE_SKILL_DIR}/.isolation-verified`.

**Forbidden in this skill's parent context:**
- ❌ `Playwright:browser_take_screenshot` (default returns image inline) — wrap it in a Task subagent
- ❌ `Read` on `*.png/.jpg/.webp/.gif/.bmp/.svg` from any path — Task subagent reads, summarizes
- ❌ Markdown reports with `![](path.png)` shown to parent — only print absolute filesystem paths
- ❌ `chrome-devtools:take_screenshot` — same Task wrapper rule

**Approved patterns:**

```
PATTERN A — text-only browser exploration (default 90% of work)
  Playwright:browser_navigate / browser_snapshot (ARIA tree → text)
  Playwright:browser_evaluate (DOM scrape → JSON)
  axe-core via spawned npx process → JSON violations
  console / network listeners → JSON
  → ALL outputs are text. No image budget cost.

PATTERN B — vision genuinely required (max 3-5 times per run)
  Task tool, subagent_type: "general-purpose", prompt:
    "Read ONE image at <absolute path>. Output: <severity>: <symptom> in <selector> at <viewport>.
     One line. No preamble. Do not return the image."
  → subagent burns its own image cap, parent stays clean.

PATTERN C — pixel-diff baseline (deterministic, scriptable)
  Spec uses toHaveScreenshot() — Playwright reports diff% as TEXT in JSON output.
  Diff > threshold → run Pattern B on the failed image only.
```

If you ever feel tempted to call `browser_take_screenshot` from this skill's parent context "just to check" — **STOP**. That single call costs the user a future `/compact`. Use `browser_snapshot` (ARIA tree) instead. If that's not enough, dispatch Pattern B.

If `${CLAUDE_SKILL_DIR}/.isolation-verified` is missing, run **Step 0** before any browser work.

## Step 0 — Image isolation self-test (once per install)

Skip if `Isolation verified: yes` above. Otherwise:

1. `bash -c 'python "${CLAUDE_SKILL_DIR}/scripts/_image_isolation_check.py" --gen-fixtures'`
2. Dispatch a Task subagent with this exact prompt:
   > "Read these 3 files with the Read tool and return one short text description per file: `${CLAUDE_SKILL_DIR}/fixtures/iso-test/a.png`, `${CLAUDE_SKILL_DIR}/fixtures/iso-test/b.png`, `${CLAUDE_SKILL_DIR}/fixtures/iso-test/c.png`. Output 3 lines, no preamble."
3. Verify response is 3 lines of text (no inline images leaked back).
4. `bash -c 'python "${CLAUDE_SKILL_DIR}/scripts/_image_isolation_check.py" --mark-verified'`

If step 3 returns inline images instead of text → STOP, escalate to user, do not run any further test work.

## Workflow

Copy this checklist into TodoWrite at session start; tick as you go.

- [ ] **1. State probe.** Read the auto-injected table above. Identify mode:
   - No `tests/` AND no `playwright.config.ts` → **BOOTSTRAP**
   - Both present, requested flow is covered by existing specs → **REPLAY**
   - Both present, requested flow is new → **HYBRID**
- [ ] **2. (BOOTSTRAP only)** Scaffold from `${CLAUDE_SKILL_DIR}/templates/`:
    - **Auth detection first:** read `.env.test`. If `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` are present → **AUTHED FLOW**; if both missing → **PUBLIC FLOW**.
    - **AUTHED FLOW:**
        - `playwright.config.ts.tmpl` → `playwright.config.ts` (has setup project + storageState)
        - `auth.setup.ts.tmpl` → `tests/auth.setup.ts`
        - `fixture.ts.tmpl` → `tests/fixtures/index.ts`
        - Run `tests/auth.setup.ts` once → `playwright/.auth/user.json`
    - **PUBLIC FLOW:**
        - `playwright.config.public.ts.tmpl` → `playwright.config.ts` (no setup, no storageState)
        - Skip `auth.setup.ts` and `fixtures/`. Specs import directly from `@playwright/test`.
    - Substitute `__PROJECT_BASE_URL__` etc. from probe or `.env.test`
    - `npm i -D @playwright/test @axe-core/playwright dotenv`
    - `npx playwright install chromium webkit`
- [ ] **3. Scope.** Decide what to test:
   - Specific URL passed by user → that route only
   - "test the app" → discover from sitemap/`git diff HEAD~1` for changed routes
   - First run → minimal critical-path: home + auth + one main flow
- [ ] **4. Dev server up.** `python "${CLAUDE_SKILL_DIR}/scripts/with_server.py" --help`. Use it; **do not read its source unless `--help` doesn't cover the case.**
- [ ] **5a. EXPLORATORY** (BOOTSTRAP / new flow in HYBRID): use **Playwright MCP** with `Playwright:browser_snapshot` (ARIA tree, text). Walk the flow, generate POM in `tests/pages/<Page>.ts`, generate spec in `tests/specs/<flow>.spec.ts`. **Generate locators from ARIA tree refs you actually saw** — do NOT use generic regex like `getByPlaceholder(/john doe|name|имя/i)`, they cause strict-mode violations on first run. Either use exact strings from the snapshot OR add `.first()` explicitly. Run the spec once to confirm green.
- [ ] **5b. REPLAY**: `npx playwright test --reporter=list,json,html`. **No Playwright MCP, no LLM browser actions.**
- [ ] **6. A11y** on each visited page: deterministic `@axe-core/playwright` (in spec) + qualitative checks via nested subagent if alt-text/heading/focus suspect. See `reference/a11y-patterns.md`.
- [ ] **7. Console + network.** Listeners attach BEFORE `page.goto()` (mandatory). Pipe captured logs through `python "${CLAUDE_SKILL_DIR}/scripts/triage_console.py" --help`.
- [ ] **8. Visual.** Default `toHaveScreenshot()` in spec. Diff fired → `python "${CLAUDE_SKILL_DIR}/scripts/visual_diff.py" --classify` spawns nested subagent on each failed image (text verdict only). Argos opt-in via `VISUAL_DIFF=argos`.
- [ ] **9. Fingerprint + diff.** `python "${CLAUDE_SKILL_DIR}/scripts/fingerprint_bugs.py" --current reports/<curr>/raw.json --previous reports/<prev>/bugs.json --out reports/<curr>/bugs.json`.
- [ ] **10. Report.** `python "${CLAUDE_SKILL_DIR}/scripts/generate_report.py" --bugs bugs.json --diff diff.json --out reports/<run-id>`. Print absolute path to `index.html`.

## Decision tree

```
detect_state.py → JSON
  ├─ no tests/ and no config       → BOOTSTRAP (full first run)
  ├─ tests/ + specs cover scope    → REPLAY (npx playwright test)
  └─ tests/ + new flow requested   → HYBRID (replay existing + explore new)
```

## MCP usage rules

- State **"using Playwright MCP"** explicitly the first time you reach for browser tools in a session. Without this, Claude often shells `npx playwright` instead.
- **Always** use fully-qualified names: `Playwright:browser_navigate`, `Playwright:browser_snapshot`, NOT bare `browser_navigate`.
- Default to `Playwright:browser_snapshot` (ARIA tree → text). Use `Playwright:browser_take_screenshot` ONLY when:
  1. Pixel-diff baseline establishment, AND
  2. Output destination is filesystem (`screenshot_path` argument), NOT inline.
- Use `chrome-devtools:performance_start_trace` ONLY for diagnostic flows (slow LCP, CORS, memory leak, sourcemap-resolved stacks). Don't use it for general exploration — its tokens are higher than Playwright MCP.

## Anti-patterns — DO NOT GENERATE

- ❌ `await page.waitForTimeout(2000)` — use web-first assertions
- ❌ `page.locator('div.btn-primary > span:nth-child(2)')` — use `getByRole`
- ❌ UI login per test — use `storageState` fixture
- ❌ Reading source of black-box scripts before trying `--help`
- ❌ Embedding credentials in spec files — read from `process.env` (loaded via `.env.test`)
- ❌ Generating tests outside `tests/specs/` — CI globs may miss them
- ❌ Returning screenshots inline to parent context — see Image budget protection
- ❌ `expect.poll` without timeout — flaky
- ❌ `nth(0)` / `first()` / `last()` without scoping via `.filter()`
- ❌ One-mega-test that does login + onboarding + checkout — split per flow

## Locator priority (enforce in generated specs)

1. `getByRole('button', { name: 'Sign in' })` — survives redesigns, aligns with a11y
2. `getByLabel`, `getByPlaceholder` — form fields
3. `getByText`, `getByAltText`, `getByTitle` — content-anchored
4. `getByTestId` — when semantics unavailable; require `data-testid` in app code
5. CSS/XPath — only with explicit code-comment justification, scoped via `.filter()`

## Black-box scripts (run with `--help` first; do not read source)

- `scripts/detect_state.py --json` — project state JSON
- `scripts/with_server.py --frontend 3000 --backend 8000` — server lifecycle
- `scripts/run_suite.py --out reports/<run-id> --project chromium-desktop` — wraps `playwright test`
- `scripts/triage_console.py --input console.json` — noise filter + LLM long tail
- `scripts/visual_diff.py --classify reports/<run-id>` — pixel diff + nested-subagent classification
- `scripts/fingerprint_bugs.py --current curr.json --previous prev.json` — bug dedup + diff
- `scripts/generate_report.py --bugs bugs.json --diff diff.json --out reports/<run-id>` — markdown + html
- `scripts/_image_isolation_check.py --verify` — image budget contract self-check

## When to dispatch a Task subagent

This skill runs in the parent chat context (no automatic fork). Always dispatch a Task subagent (`general-purpose`) for:
- **Any browser work that may produce screenshots** — see Image budget protection (mandatory wrap)
- **Test suites > 30 specs OR > 2 minutes wall-clock** — keep token budget under 25k auto-compaction ceiling
- **Vision classification of a single screenshot** — Pattern B in Image budget protection
- **Long-tail console triage that needs LLM inference per message** — batch-spawn one subagent per chunk

## Credentials — universal, no project hardcoding

Read in this order, first hit wins:
1. `<project>/.env.test` (project-scoped)
2. `${TEST_CREDENTIALS_FILE}` env var pointing to a global file
3. Prompt user once, write to `<project>/.env.test`, add to `.gitignore`

Required keys per project: `TEST_BASE_URL`, `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`. Optional: `TEST_API_LOGIN_PATH` (default `/api/auth/login`), `TEST_API_TOKEN_FIELD` (default `access_token`), `TEST_USER_AGENT_KIND` (default `desktop`).

## References (load on demand, do not pre-read)

- `reference/playwright-patterns.md` — locator priority, web-first assertions, anti-flake patterns
- `reference/auth-strategies.md` — Day 2: API-login, JWT, storageState, OAuth fallback notes
- `reference/a11y-patterns.md` — Day 3: axe + qualitative checks via nested subagent
- `reference/responsive-checklist.md` — Day 3: viewports, touch targets, overflow detection
- `reference/console-noise-patterns.md` — Day 3: ignore-list defaults
- `reference/stack-specific.md` — Day 4: Next.js, FastAPI, Telegram WebApp, WebSocket/SSE
- `reference/reporting.md` — Day 4: JSON schema, markdown skeleton, tracker mappings
