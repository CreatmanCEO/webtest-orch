# Contributing to webtest-orch

Thanks for considering a contribution. This document is short on purpose — read it once, then move fast.

## Quick start

1. Fork the repo, clone your fork.
2. Install dependencies: Python 3.10+, Node.js 18+, Claude Code CLI.
3. Install the skill locally for testing:
   ```bash
   bash install.sh --symlink   # symlinks live source into ~/.claude/skills/
   ```
4. Make changes. Re-run the skill in any project to test.

## What we want

| Welcome | Less welcome |
|---|---|
| Bug reports with reproduction steps | "doesn't work for me" without context |
| New stack-specific patterns (Supabase, NextAuth, Clerk, etc.) | Speculative refactors of working code |
| OS compatibility reports (Linux/macOS/Windows variants) | Style-only changes without functional reason |
| New `console-noise-patterns.md` patterns from your apps | Re-litigating architectural decisions |
| Test cases for `scripts/*.py` | New dependencies without strong justification |

## Pull request workflow

1. **One PR = one concern.** Don't bundle a bug fix with a refactor.
2. **Update CHANGELOG.md** under `[Unreleased]`. The first line of your CHANGELOG entry is your PR description.
3. **Add tests if you touched a Python script.** Smoke-tests live in `tests/python/` (coming in `0.2.0`); for now, hand-verify and document what you ran.
4. **Don't add LLM calls inside scripts.** Skill scripts MUST stay deterministic. LLM work happens via Task subagents dispatched by the orchestrator, not inside `*.py`.
5. **Image-budget protection is non-negotiable.** Any change that lets screenshots leak into the parent chat context will be reverted. Read `SKILL.md` § "Image budget protection" first.
6. **Sign-off.** Add a `Co-authored-by:` trailer if multiple humans worked on the PR.

## Naming and structure

- New script: `scripts/<verb>_<noun>.py`. Must accept `--help` and return useful info.
- New reference doc: `reference/<topic>.md`. Add a one-line entry in `SKILL.md` § References.
- New template: `templates/<file>.<ext>.tmpl`. Document its placeholders at the top with `// PLACEHOLDERS: __NAME1__ __NAME2__`.

## Review SLA

- **Bug reports:** triaged within 7 days.
- **PRs:** first review within 14 days. We're a small project; please be patient.

## Code of Conduct

By participating, you agree to abide by [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).

## Releasing (maintainers only)

1. Bump version in `package.json` (when published).
2. Move `[Unreleased]` items into a new `[X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md`.
3. `git tag vX.Y.Z && git push --tags`.
4. GitHub Actions creates the release.
