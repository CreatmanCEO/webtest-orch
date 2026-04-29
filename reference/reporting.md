# Reporting reference

> Loaded on demand. Day 4. JSON schema + Markdown skeleton + tracker mappings.

## Output triple per run

After every run, the skill emits three files in `reports/<run-id>/`:

1. **`bugs.json`** — machine-readable, normalized bug list with run-diff state
2. **`report.md`** — human-readable summary, severity table, top issues with reproducer
3. **`index.html`** — self-contained HTML wrapper around `report.md`, opens in any browser

Plus optional artifacts:
- `screenshots/` — failure screenshots (paths only in markdown, never inline)
- `traces/` — Playwright `.zip` traces for replay debugging
- `network/` — HAR files
- `vision-tasks.json` — pending vision classifications (if any)
- `diff.json` — run-diff summary (new/regression/persisting/fixed counts)

## bugs.json schema (v1.0.0)

```json
{
  "runId": "run-2026-04-28-1430",
  "bugs": [
    {
      "schemaVersion": "1.0.0",
      "id": "BUG-a3f9c2b1",
      "fingerprintHash": "a3f9c2b1",
      "title": "Auth — login flow > rejects invalid creds",
      "specFile": "tests/specs/auth.spec.ts",
      "specTitle": "rejects invalid creds",
      "project": "chromium-desktop",
      "status": "failed",

      "severity": "S0",
      "priority": "P0",
      "category": "functional",

      "error": {
        "message": "TimeoutError: locator.click ...",
        "stack": "...",
        "snippet": "await page.getByRole(...).click();",
        "location": { "file": "tests/specs/auth.spec.ts", "line": 42 }
      },

      "duration_ms": 10500,
      "retry": 0,
      "screenshots": ["./screenshots/a3f9c2b1.png"],
      "traces": ["./traces/a3f9c2b1.zip"],

      "discoveredAt": "2026-04-28T14:30:22Z",
      "firstSeenRunId": "run-2026-04-28-1430",
      "lastSeenRunId": "run-2026-04-28-1430",
      "occurrenceCount": 1,

      "diff": {
        "state": "new",
        "previousRunId": "run-2026-04-26-0902"
      },

      "trackerMappings": {
        "linear": { "priority": 1 },
        "github": { "labels": ["bug", "severity/s0", "priority/p0"] },
        "jira": { "issueType": "Bug", "priorityName": "Highest" }
      }
    }
  ]
}
```

## Severity heuristics (S0–S3)

| Severity | When the skill assigns it |
|---|---|
| **S0 Critical** | Title/error contains: `auth`, `login`, `logout`, `checkout`, `payment`, 5xx response, "data loss", "uncaught" + critical flow |
| **S1 Major** | Form non-functional, primary nav broken, 404 on main routes, hydration mismatch, CORS, CSP violation |
| **S2 Moderate** | Validation message wrong, secondary feature degraded, a11y violations (axe), 4xx (non-auth), CSP inline |
| **S3 Minor** | Pixel/visual diffs, alignment shifts, color contrast warnings (non-blocking) |

Override severity by hand-editing `bugs.json` — fingerprint stays stable, severity is derived but writeable.

## Priority mapping (P0–P3)

Default 1:1 with severity. Tracker-specific:

| Internal | Linear | GitHub label | Jira |
|---|---:|---|---|
| P0 | `1` (Urgent) | `priority/p0` | Highest |
| P1 | `2` (High) | `priority/p1` | High |
| P2 | `3` (Medium) | `priority/p2` | Medium |
| P3 | `4` (Low) | `priority/p3` | Low |

## Run diff states

| State | Meaning |
|---|---|
| `new` | Bug not present in previous run |
| `regression` | Bug present in previous run, was marked `fixed`, now back |
| `persisting` | Bug present in both previous and current run |
| `fixed` | Bug present in previous run, absent in current run, was open |

A "fixed" record gets emitted in current `bugs.json` so the diff is auditable. Next run won't re-mark it fixed (state is sticky once set).

## Markdown skeleton (rendered by `generate_report.py`)

```markdown
# Test run — Example App
**Run ID:** run-2026-04-29-1430

**Verdict:** ❌ NOT SHIP-READY — S0 critical bugs present

## 📊 Summary
| Metric | Value |
|---|---:|
| Total bugs | 9 |
| 🔴 S0 Critical | 1 |
| 🟠 S1 Major | 3 |
| 🟡 S2 Moderate | 4 |
| 🟢 S3 Minor | 1 |

## 🔁 Run diff
| State | Count |
|---|---:|
| 🆕 New | 4 |
| 🚨 Regression | 1 |
| ⚠️ Persisting | 4 |
| ✅ Fixed | 2 |

## 🚨 Open issues

### 1. [BUG-a3f9c2b1] S0/P0 — Auth login non-functional 🔴 🆕
- State: `new` · Occurrences: 1
- Spec: `tests/specs/auth.spec.ts` :: rejects invalid creds
- Project: `chromium-desktop`

```
TimeoutError: ...
```

[📸 screenshot](./screenshots/a3f9c2b1.png) · [🎬 trace](./traces/a3f9c2b1.zip)
```

## Filing bugs to trackers

The skill emits `trackerMappings` per bug. To file:

### Linear
```bash
jq -r '.bugs[] | select(.severity=="S0") | "lin issue create \"\(.title)\" --priority \(.trackerMappings.linear.priority) --description-file <(echo \"\(.error.message)\")"' bugs.json
```

### GitHub Issues
```bash
jq -c '.bugs[] | select(.severity == "S0")' bugs.json | while IFS= read -r b; do
  title=$(echo "$b" | jq -r .title)
  labels=$(echo "$b" | jq -r '.trackerMappings.github.labels | join(",")')
  body=$(echo "$b" | jq -r '"## Error\n\n```\n\(.error.message)\n```\n\nSpec: `\(.specFile)`"')
  gh issue create --title "$title" --label "$labels" --body "$body"
done
```

### Jira (via `jira-cli`)
```bash
jq -c '.bugs[]' bugs.json | while IFS= read -r b; do
  title=$(echo "$b" | jq -r .title)
  pri=$(echo "$b" | jq -r '.trackerMappings.jira.priorityName')
  jira issue create -s "$title" -t Bug -P "$pri"
done
```

These are illustrative — the skill does NOT auto-file in v1. User decides which bugs are worth tracker entries.

## Schema versioning

`schemaVersion` is per-bug to support partial migrations. The skill currently
emits `1.0.0`. Breaking changes (rename, type swap) bump major; additive (new
field) bumps minor.
