# Changelog

All notable changes to this project will be documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for `0.3.0`
- Vision-classifier auto-loop (`vision_dispatch.py`)
- Console LLM auto-triage (`console_llm_triage.py` with batched subagent)
- Performance / Lighthouse audit script
- Tracker integration CLI (`file_bugs.py --linear / --github / --jira`)
- Regression watchlist mechanism (sticky fixed → escalate on regression)
- Layout integrity assertions (max-width, icon grouping patterns)

## [0.2.0-beta] - 2026-04-29

Functional gaps closed based on dogfooding feedback from two real apps. Pre-OSS
v1 hardening — zero false positives in skill core, 113 passing tests, green CI
on Linux/macOS/Windows.

### Added
- **Supabase Auth Pattern 1.5** — `auth.setup.ts.tmpl` auto-detects `SUPABASE_URL`
  + `SUPABASE_ANON_KEY`, hits `/auth/v1/token?grant_type=password` with `apikey`
  header, polls localStorage 45s for `sb-<ref>-auth-token` (no assumption of
  URL change post-login). Documented in `auth-strategies.md` Pattern 1.
- **Onboarding overlay state-seeding** — `seedOnboardingFlags()` helper in
  `auth.setup.ts.tmpl` auto-flips `localStorage` keys matching common patterns
  (`*-features-discovered`, `*-onboarding-complete`, `*-tour-seen`,
  `*-hints-seen`, `*-welcome-dismissed`). Override via `TEST_ONBOARDING_FLAGS`
  JSON env var. Without this, apps with feature-tour overlays fail every spec.
- **Severity annotation mechanism** — three ways to override the heuristic:
  1. `[severity:S0]` inline tag in `issues.push(...)` lines
  2. `[severity:S0]` in spec test name
  3. `// @severity: S0` comment preceding `test('...')` in spec file
  `fingerprint_bugs.py --project-root` flag controls where to look for spec files.
- **Spec generation contract** in SKILL.md — non-negotiable list of elements
  every generated spec MUST contain (console + network listeners before goto,
  axe scan, issues[] collector, hard `expect(issues).toEqual([])` at end).
  Closes the gap where Claude wrote specs from scratch and silently skipped
  the audit features.
- **`scripts/preflight.py`** — quick env + base-URL HEAD check before scaffolding.
  Fails fast with actionable hints if `TEST_BASE_URL` is unreachable, auth env
  missing, or Supabase key looks malformed.
- **Tabs-vs-buttons reference note** in `playwright-patterns.md` — handles SPAs
  with visual tabs but no `role="tab"` (logs as a11y soft finding instead of failing).
- **WebSocket DOM-fallback strategy** in `stack-specific.md` — when WS frames are
  binary/encrypted/proprietary, assert on DOM mutations instead of frames.
- **Pydantic, Next.js 15 Turbopack, Supabase realtime, browser-extension,
  ResizeObserver, AbortError** patterns added to `console-noise-patterns.md`
  default ignore-list.
- **Run artefact summary** at end of `run_suite.py` — prints all generated paths
  + next-step commands so users don't have to `ls reports/`.

### Fixed
- **`generate_report.py` doc drift** — SKILL.md step 10 now matches the actual
  `--run-dir` CLI signature.
- **Anchored regex** in auth UI fallback (`/^(sign in|log in|войти|вход)$/i`) —
  no longer matches "Sign up" / "Sign in with Google".
- **Skill-dir resolution** in `detect_state.py` — populates `skillDir` from
  `__file__` when `CLAUDE_SKILL_DIR` env is unset, instead of returning `null`.
  Fixes `Isolation verified: false` mismatch reported by Lingua tester.
- **Image-budget rule wording** in SKILL.md — clarifies that on-disk
  auto-captures (which nobody `Read`s) are FREE; the cost is inline returns.
- **Fingerprint regex** for node counts now matches both ASCII `(3x nodes)` and
  Unicode `(3× nodes)`.

### Tests
- 19 new tests covering severity overrides, skill-dir resolution, preflight
  module. Total: 113 passing across 10 scripts.

## [0.1.0-beta] - 2026-04-29

## [0.1.0-beta] - 2026-04-29

Initial public beta. Validated end-to-end on a real production app
(static Next.js portfolio + a SaaS chat app via dogfooding).

### Added
- `SKILL.md` — Claude Code skill workflow (181 lines)
- `README.md` — user-facing documentation
- `install.sh` — copy/symlink installer with MCP preflight check
- 9 black-box scripts:
  - `detect_state.py` — project state probe (JSON / human modes)
  - `with_server.py` — dev-server lifecycle (frontend + backend)
  - `_image_isolation_check.py` — image-budget contract self-test
  - `run_suite.py` — wraps `npx playwright test`, normalizes output, ANSI-strip,
    extracts individual issues from `issues[]` collector pattern
  - `fingerprint_bugs.py` — composite SHA-256 fingerprints, severity heuristics
    (a11y impact-aware), Linear/GitHub/Jira tracker mappings, run-diff
  - `triage_console.py` — default ignore-list (GTM, Stripe, Sentry, dev-mode
    React, source-map 404s); bug-pattern classifier (hydration, CORS, CSP, 5xx)
  - `visual_diff.py` — locates `toHaveScreenshot()` failures, prepares
    vision-classification tasks
  - `vision_classify.py` — validates verdict format from Task subagent
  - `generate_report.py` — emits `report.md` + `index.html` + diff section
- 7 reference docs: Playwright patterns, auth strategies, a11y patterns,
  responsive checklist, console noise patterns, stack-specific (Next.js,
  FastAPI, Telegram WebApp, WS/SSE, TTS), reporting (JSON schema + tracker
  mappings)
- 6 templates: `playwright.config.ts.tmpl` (with auth), `playwright.config.public.ts.tmpl`
  (no auth), `auth.setup.ts.tmpl` (API-first, UI fallback), `fixture.ts.tmpl`,
  `pom.ts.tmpl`, `spec.ts.tmpl` (issues[] collector pattern)

### Image-budget protection
- All browser work is delegated to a Task subagent (not a frontmatter
  `context: fork` directive — that field is not honoured by all Claude Code
  builds yet). Parent chat never receives inline images.

### Known limitations
- Playwright MCP must be installed separately (`claude mcp add playwright`).
- Documentation drift: `generate_report.py` argument signature does not match
  `SKILL.md` step 10 wording; will be reconciled in `0.2.0`.
- Severity is structurally inferred (no LLM pass); P0 product regressions can
  be misclassified as S2 unless the spec is annotated; `0.2.0` adds annotation
  parsing.
- Onboarding overlays in target apps will fail every spec until the user adds
  state-seeding to `auth.setup.ts`; `0.2.0` adds an explicit hook block.
- macOS / Linux installers untested in CI; help wanted (see
  `os-compatibility-report` issue template).

[Unreleased]: https://github.com/CreatmanCEO/webtest-orch/compare/v0.2.0-beta...HEAD
[0.2.0-beta]: https://github.com/CreatmanCEO/webtest-orch/compare/v0.1.0-beta...v0.2.0-beta
[0.1.0-beta]: https://github.com/CreatmanCEO/webtest-orch/releases/tag/v0.1.0-beta
