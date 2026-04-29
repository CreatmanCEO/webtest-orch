#!/usr/bin/env bash
# install.sh — install webtest-orch into Claude Code skill dirs.
#
# Copies (or symlinks) this directory into ~/.claude/skills/webtest-orch/
# and verifies that required MCP servers are registered.
#
# Usage:
#   bash install.sh                  # copy
#   bash install.sh --symlink        # symlink (preferred during development)
#   bash install.sh --check-only     # verify state, change nothing
#
set -euo pipefail

MODE="copy"
for arg in "$@"; do
  case "$arg" in
    --symlink)    MODE="symlink" ;;
    --check-only) MODE="check"   ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${HOME}/.claude/skills/webtest-orch"

c_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
c_green() { printf '\033[32m%s\033[0m\n' "$*"; }
c_yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
c_dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

mcp_has() {
  local name="$1"
  command -v claude >/dev/null 2>&1 || return 2
  claude mcp list 2>/dev/null | grep -qE "^${name}[:[:space:]]|^${name}$" || return 1
  return 0
}

check_python() {
  if command -v python3 >/dev/null 2>&1; then
    return 0
  elif command -v python >/dev/null 2>&1; then
    return 0
  else
    c_red "✗ python (3.x) not found on PATH"
    return 1
  fi
}

check_mcps() {
  local missing=0
  for srv in playwright chrome-devtools; do
    if mcp_has "$srv"; then
      c_green "✓ MCP server present: $srv"
    else
      rc=$?
      if [[ $rc == 2 ]]; then
        c_yellow "? \`claude\` CLI not found — skipping MCP check"
        return 0
      fi
      c_red "✗ MCP server missing: $srv"
      missing=$((missing + 1))
    fi
  done
  if (( missing > 0 )); then
    echo
    c_yellow "Install missing MCPs with:"
    echo "  claude mcp add playwright npx @playwright/mcp@latest"
    echo "  claude mcp add chrome-devtools npx chrome-devtools-mcp@latest"
    return 1
  fi
}

install_copy() {
  c_dim "Copying $SOURCE_DIR → $TARGET_DIR"
  mkdir -p "$(dirname "$TARGET_DIR")"
  if [[ -e "$TARGET_DIR" || -L "$TARGET_DIR" ]]; then
    c_yellow "Existing $TARGET_DIR will be replaced (backup → ${TARGET_DIR}.bak)"
    rm -rf "${TARGET_DIR}.bak"
    mv "$TARGET_DIR" "${TARGET_DIR}.bak"
  fi
  cp -R "$SOURCE_DIR" "$TARGET_DIR"
  c_green "✓ Skill installed at $TARGET_DIR"
}

install_symlink() {
  c_dim "Symlinking $SOURCE_DIR → $TARGET_DIR"
  mkdir -p "$(dirname "$TARGET_DIR")"
  if [[ -e "$TARGET_DIR" || -L "$TARGET_DIR" ]]; then
    if [[ -L "$TARGET_DIR" && "$(readlink "$TARGET_DIR")" == "$SOURCE_DIR" ]]; then
      c_green "✓ Symlink already correct"
      return 0
    fi
    c_yellow "Existing $TARGET_DIR will be replaced (backup → ${TARGET_DIR}.bak)"
    rm -rf "${TARGET_DIR}.bak"
    mv "$TARGET_DIR" "${TARGET_DIR}.bak"
  fi
  ln -s "$SOURCE_DIR" "$TARGET_DIR"
  c_green "✓ Symlink created at $TARGET_DIR"
}

case "$MODE" in
  check)
    check_python || true
    check_mcps   || true
    if [[ -e "$TARGET_DIR" ]]; then
      c_green "✓ Skill present at $TARGET_DIR"
    else
      c_yellow "skill not yet installed at $TARGET_DIR"
    fi
    ;;
  copy)
    check_python
    install_copy
    check_mcps || c_yellow "Continuing despite missing MCPs — install them before first run."
    echo
    c_dim "Next: open Claude Code in any project and say \"test the app\" to trigger the skill."
    ;;
  symlink)
    check_python
    install_symlink
    check_mcps || c_yellow "Continuing despite missing MCPs — install them before first run."
    echo
    c_dim "Symlink mode: edits in $SOURCE_DIR are picked up live."
    ;;
esac
