#!/usr/bin/env node
/**
 * webtest-orch CLI — installs the Claude Code skill into ~/.claude/skills/.
 *
 * Subcommands:
 *   install   — copy or symlink the skill into ~/.claude/skills/webtest-orch/
 *   uninstall — remove the installed skill (NOT the npm package)
 *   status    — print install state + MCP availability
 *   version   — print package version
 *   help      — usage
 *
 * Usage:
 *   npx webtest-orch install
 *   npx webtest-orch install --symlink   (development; needs admin on Windows)
 *   npx webtest-orch status
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { execSync, spawnSync } = require('node:child_process');

const PKG_ROOT = path.resolve(__dirname, '..');
const PKG_JSON = require(path.join(PKG_ROOT, 'package.json'));
const TARGET_DIR = path.join(os.homedir(), '.claude', 'skills', 'webtest-orch');

// Files/dirs that ship with the skill (mirrors `files` in package.json)
const SKILL_PAYLOAD = [
  'SKILL.md',
  'README.md',
  'LICENSE',
  'CHANGELOG.md',
  'install.sh',
  'scripts',
  'reference',
  'templates',
  'examples',
];

const COLORS = {
  red: (s) => `\x1b[31m${s}\x1b[0m`,
  green: (s) => `\x1b[32m${s}\x1b[0m`,
  yellow: (s) => `\x1b[33m${s}\x1b[0m`,
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
};

function copyRecursive(src, dst) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dst, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dst, entry));
    }
  } else {
    fs.copyFileSync(src, dst);
  }
}

function backupExisting(target) {
  if (!fs.existsSync(target)) return null;
  const backup = `${target}.bak`;
  if (fs.existsSync(backup)) fs.rmSync(backup, { recursive: true, force: true });
  fs.renameSync(target, backup);
  return backup;
}

function checkMcps() {
  const result = spawnSync('claude', ['mcp', 'list'], {
    encoding: 'utf-8',
    shell: process.platform === 'win32',
  });
  if (result.status !== 0 || !result.stdout) {
    console.log(COLORS.yellow('? `claude` CLI not found on PATH — skipping MCP check.'));
    console.log(COLORS.dim('  Install Claude Code first: https://docs.claude.com/en/docs/claude-code'));
    return { ok: true, claudeAvailable: false };
  }
  const out = result.stdout;
  const have = (name) => new RegExp(`^${name}[\\s:]`, 'm').test(out);
  const missing = [];
  if (!have('playwright')) missing.push('playwright');
  if (!have('chrome-devtools')) missing.push('chrome-devtools');
  for (const name of ['playwright', 'chrome-devtools']) {
    if (have(name)) console.log(COLORS.green(`✓ MCP: ${name}`));
  }
  if (missing.length) {
    console.log();
    console.log(COLORS.yellow('Missing MCP servers. Install with:'));
    for (const name of missing) {
      const cmd = name === 'playwright'
        ? 'claude mcp add --scope user playwright npx @playwright/mcp@latest'
        : 'claude mcp add --scope user chrome-devtools npx chrome-devtools-mcp@latest';
      console.log(`  ${cmd}`);
    }
  }
  return { ok: missing.length === 0, missing, claudeAvailable: true };
}

function cmdInstall(args) {
  const useSymlink = args.includes('--symlink');
  console.log(`webtest-orch v${PKG_JSON.version}`);
  console.log(COLORS.dim(`source: ${PKG_ROOT}`));
  console.log(COLORS.dim(`target: ${TARGET_DIR}`));

  fs.mkdirSync(path.dirname(TARGET_DIR), { recursive: true });

  if (useSymlink) {
    if (process.platform === 'win32') {
      console.log(COLORS.yellow(
        '! --symlink on Windows requires Developer Mode or admin shell. ' +
        'Use plain `install` (copy mode) if you hit EPERM.',
      ));
    }
    const backup = backupExisting(TARGET_DIR);
    if (backup) console.log(COLORS.dim(`backed up existing → ${backup}`));
    try {
      fs.symlinkSync(PKG_ROOT, TARGET_DIR, 'dir');
      console.log(COLORS.green(`✓ Symlinked ${TARGET_DIR}`));
    } catch (e) {
      console.error(COLORS.red(`✗ Symlink failed: ${e.message}`));
      console.error(COLORS.yellow('Falling back to copy mode...'));
      cmdInstall(args.filter((a) => a !== '--symlink'));
      return;
    }
  } else {
    const backup = backupExisting(TARGET_DIR);
    if (backup) console.log(COLORS.dim(`backed up existing → ${backup}`));
    fs.mkdirSync(TARGET_DIR, { recursive: true });
    for (const item of SKILL_PAYLOAD) {
      const src = path.join(PKG_ROOT, item);
      if (!fs.existsSync(src)) continue;
      copyRecursive(src, path.join(TARGET_DIR, item));
    }
    console.log(COLORS.green(`✓ Skill installed at ${TARGET_DIR}`));
  }

  console.log();
  console.log('Checking MCP servers...');
  checkMcps();

  console.log();
  console.log(COLORS.bold('Next steps:'));
  console.log('  1. Restart Claude Code (skills load at session start).');
  console.log('  2. In any project, create `.env.test` with TEST_BASE_URL.');
  console.log('  3. Say "test the app" or run /test-app.');
  console.log();
  console.log(COLORS.dim('Docs: https://github.com/CreatmanCEO/webtest-orch#readme'));
}

function cmdUninstall() {
  if (!fs.existsSync(TARGET_DIR)) {
    console.log(COLORS.yellow(`Nothing to uninstall — ${TARGET_DIR} does not exist.`));
    return;
  }
  fs.rmSync(TARGET_DIR, { recursive: true, force: true });
  console.log(COLORS.green(`✓ Removed ${TARGET_DIR}`));
  console.log(COLORS.dim('The npm package itself is untouched. Use `npm uninstall -g webtest-orch` to remove it.'));
}

function cmdStatus() {
  console.log(`webtest-orch v${PKG_JSON.version}`);
  if (fs.existsSync(TARGET_DIR)) {
    const stat = fs.lstatSync(TARGET_DIR);
    const kind = stat.isSymbolicLink() ? 'symlink' : 'copy';
    console.log(COLORS.green(`✓ Skill installed (${kind}): ${TARGET_DIR}`));
    const skillMd = path.join(TARGET_DIR, 'SKILL.md');
    if (fs.existsSync(skillMd)) {
      const content = fs.readFileSync(skillMd, 'utf-8');
      const m = content.match(/^name:\s*(.+)$/m);
      if (m) console.log(COLORS.dim(`  skill name: ${m[1].trim()}`));
    }
  } else {
    console.log(COLORS.yellow(`✗ Skill not installed (target: ${TARGET_DIR})`));
    console.log(COLORS.dim('  Run: npx webtest-orch install'));
  }
  console.log();
  console.log('MCP servers:');
  checkMcps();
}

function cmdHelp() {
  console.log(`webtest-orch v${PKG_JSON.version}`);
  console.log();
  console.log('Usage:');
  console.log('  npx webtest-orch <command> [options]');
  console.log();
  console.log('Commands:');
  console.log('  install            Copy skill into ~/.claude/skills/webtest-orch/');
  console.log('  install --symlink  Symlink instead of copy (development)');
  console.log('  uninstall          Remove the installed skill');
  console.log('  status             Show install state + MCP availability');
  console.log('  version            Print package version');
  console.log('  help               This message');
  console.log();
  console.log('Docs: https://github.com/CreatmanCEO/webtest-orch#readme');
}

function main() {
  const [, , cmd, ...rest] = process.argv;
  switch (cmd) {
    case 'install': return cmdInstall(rest);
    case 'uninstall': return cmdUninstall();
    case 'status': return cmdStatus();
    case 'version':
    case '--version':
    case '-v': return console.log(PKG_JSON.version);
    case 'help':
    case '--help':
    case '-h':
    case undefined: return cmdHelp();
    default:
      console.error(COLORS.red(`unknown command: ${cmd}`));
      console.error(`Run "npx webtest-orch help" for usage.`);
      process.exit(2);
  }
}

main();
