# Console noise patterns reference

> Loaded on demand. Day 3.

The skill's `triage_console.py` runs each captured console / network message
against this two-tier classifier:

1. **Default ignore-list** — third-party noise that almost always means nothing
2. **Bug patterns** — known classes that map to severity directly

Anything matching neither is flagged `needs-llm` and surfaced for orchestrator
to dispatch a Task subagent for triage (cached by message hash to avoid re-spending tokens).

## Default ignore-list

These match the regexes hardcoded in `scripts/triage_console.py`. Edit the
script (or pass `--ignore-extra` from the orchestrator) to add app-specific patterns.

| Pattern | Source | Why ignore |
|---|---|---|
| `googletagmanager.com`, `google-analytics.com` | GA / GTM | Self-referential warnings, no user impact |
| `\[Stripe\.js\] .* deprecated` | Stripe SDK | Migration warnings, not page bugs |
| `sentry\.(io\|wat)` | Sentry SDK | Self-warnings about Sentry config |
| `Failed to load resource: .* favicon` | Browser | Missing favicon — cosmetic |
| `DevTools failed to load source map` | Browser dev tools | Source-map miss in dev builds |
| `Download the React DevTools` | React dev mode | Dev-only marketing message |
| `Warning: ReactDOM\.render is no longer supported` | React 18 dev mode | Migration nag |
| `Blocked a frame with origin .* from accessing` | iframe sandbox | Expected in sandboxed iframes |
| `\[HMR\]`, `\[vite\]`, `\[next\]: hot-update` | Hot module reload | Dev-only |
| `Permission denied to access property .* on cross-origin` | Cross-origin frame | Expected |

## Bug patterns (auto-report with severity)

| Pattern | Category | Severity | Reasoning |
|---|---|---|---|
| `Hydration failed`, `Text content does not match server-rendered` | hydration-mismatch | S1 | SSR/CSR drift — broken UX after first interaction |
| `Uncaught .* TypeError`, `Cannot read prop` | js-typeerror | S0 | JavaScript broken on user path |
| `Uncaught ReferenceError` | js-reference-error | S0 | Same |
| `Uncaught SyntaxError` | js-syntax-error | S0 | Bundler regression |
| `net::ERR_FAILED`, `net::ERR_NAME_NOT_RESOLVED` | network-failure | S1 | Backend unreachable |
| `CORS .* blocked`, `Cross-Origin Request Blocked` | cors | S1 | Configuration error |
| `Refused to load .* Content Security Policy` | csp-violation | S1 | CSP misconfigured |
| `Refused to execute inline script` | csp-inline | S2 | Inline script blocked — usually 3rd-party |
| `WebSocket connection .* failed` | websocket-fail | S1 | Real-time features broken |
| `Service worker registration failed` | sw-fail | S2 | PWA / offline broken |
| HTTP 5xx | 5xx-response | S0 | Server error |
| HTTP 4xx | 4xx-response | S2 | Client error (often expected — auth flows) |

## App-specific extensions

When a project legitimately produces a recurring "noise" message, append it
via `--ignore-extra` flag to `triage_console.py`:

```bash
triage_console.py --input console.json \
  --ignore-extra "AbortError: signal is aborted" \
  --ignore-extra "ResizeObserver loop limit"
```

These are common framework artifacts that aren't user-visible.

## What goes to LLM triage

Anything that matches NEITHER ignore NOR bug patterns. Classifier marks it
`needs-llm`. The skill dispatches a Task subagent (general-purpose) with a
prompt like:

```
Classify this browser console message:
"<text>"

Return ONE line:
  ignore: <reason>          — third-party / dev-only / cosmetic
  warn: <reason>            — worth tracking but not blocking
  bug-S<0-3>: <reason>      — real user-visible problem at given severity
```

The verdict is cached by message-hash — same message in next run reuses cached
classification, costs zero tokens.

## Hard rule on LLM triage volume

Skill SHOULD NOT spawn one subagent per message — too many subagents = slow
+ wasted tokens. **Batch unknowns**: spawn ONE subagent with a list of up to
20 unique unclassified messages, get back a list of verdicts. The orchestrator
counts unique-after-hash before dispatching.

## Listener placement (mandatory)

In every spec, listeners attach BEFORE `page.goto()`. After `goto()` is too
late — early errors miss. The skill's `spec.ts.tmpl` enforces this order.

## What the skill never ignores

- Hydration mismatches — these break interactivity silently
- Uncaught JS errors — even on dev builds, these are real
- 5xx responses — even one 500 in a test run is a bug

These are surfaced regardless of ignore-list extensions.
