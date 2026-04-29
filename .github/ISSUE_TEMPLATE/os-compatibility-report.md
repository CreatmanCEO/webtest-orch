---
name: OS compatibility report
about: Tested on a non-Windows OS — share the results (good or bad)
title: "[compat] <OS> + <shell>"
labels: compatibility, beta-feedback
---

We're actively looking for cross-platform feedback during the `0.1.x` beta. Even "everything works" reports help — they let us mark an OS as smoke-tested.

## Environment

- OS: <!-- Ubuntu 22.04, macOS 14.x, Fedora 40, ... -->
- Architecture: <!-- x86_64 / arm64 -->
- Shell: <!-- bash 5.2, zsh, fish, ... -->
- Node version:
- Python version:
- Claude Code version:

## Install path

- Method: `bash install.sh` / `bash install.sh --symlink` / cloned manually
- Result:
  - [ ] `install.sh` ran cleanly
  - [ ] `claude mcp list` shows `playwright` and `chrome-devtools`
  - [ ] Skill appears in Claude Code's available skills list after restart

## First run

- Target app: <!-- public site / authed app / Supabase / NextAuth / FastAPI / ... -->
- Bootstrap result:
  - [ ] `npm i -D @playwright/test @axe-core/playwright dotenv` succeeded
  - [ ] `npx playwright install chromium` succeeded
  - [ ] `auth.setup.ts` ran without manual edits
  - [ ] First spec passed
  - [ ] `report.md` and `bugs.json` were generated

## Friction points

<!-- What did you have to fix manually? Quote shell commands or error messages. -->

## Time to first green spec

<!-- From `git clone` to first passing assertion. -->

## Anything we should add to the docs?

<!-- Edge cases that surprised you. -->
