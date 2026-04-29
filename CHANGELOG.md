# Changelog

All notable changes to this project will be documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for `0.2.0`
- Supabase Auth pattern (`auth.setup.ts.tmpl` branch on `SUPABASE_URL`)
- Onboarding-overlay state-seeding hook in auth setup template
- Severity annotation: `// @severity: S0` parsing in spec files
- Spec generation contract: console listeners + axe scan + issues collector required
- `--bugs/--diff/--out` accepted as aliases on `generate_report.py`
- Anchored regex in auth template
- Pydantic / Next.js 15 patterns in `console-noise-patterns.md`

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

[Unreleased]: https://github.com/CreatmanCEO/webtest-orch/compare/v0.1.0-beta...HEAD
[0.1.0-beta]: https://github.com/CreatmanCEO/webtest-orch/releases/tag/v0.1.0-beta
