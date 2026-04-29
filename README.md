# webtest-orch — webapp-test-orchestrator

[![CI](https://github.com/CreatmanCEO/webtest-orch/actions/workflows/ci.yml/badge.svg)](https://github.com/CreatmanCEO/webtest-orch/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0--beta-orange.svg)](./CHANGELOG.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**Universal e2e testing skill for Claude Code.** Заменяет ad-hoc промпты с Playwright MCP на одну переиспользуемую сущность для тестирования любого web-приложения (Next.js, FastAPI, статика, Telegram WebApp, и т.д.).

> ⚠️ **Public beta (`0.1.0-beta`)** — looking for early feedback, especially OS-compatibility reports. See [issue templates](.github/ISSUE_TEMPLATE/).

---

## Зачем

| До skill | После skill |
|---|---|
| Каждый раз пишешь длинный промпт «протестируй login на app, проверь a11y, console errors, мобильный viewport» | Говоришь **«test the app»** — skill сам решает что делать |
| Каждый screenshot Playwright MCP уходит в parent чат → image cap забивается на ~50–100 → `/compact` при низком расходе текста | Скриншоты остаются в Task subagent, parent видит только текст |
| Первый прогон exploratory (LLM-heavy), второй прогон — снова с нуля | Первый прогон генерирует `*.spec.ts`, второй — `npx playwright test` без LLM (~$0) |
| Bugs теряются между прогонами | Composite fingerprint + run diff → `new`/`regression`/`persisting`/`fixed` |

---

## Когда skill активируется

Скажи в Claude Code что-то вроде:

- «test the app»
- «протестируй приложение»
- «run e2e»
- «smoke test»
- «check the login flow»
- «audit accessibility»
- «test responsive»
- «find bugs in https://your-app.example.com»

Skill сработает автоматически — даже если ты не упомянул Playwright или Claude Code.

Также есть slash-команда: **`/test-app`** (alias через frontmatter `trigger`).

---

## Установка (один раз)

### 1. Skill files

```bash
# Из корня репо webapp-test-orchestrator/
bash install.sh
```

Установит skill в `~/.claude/skills/webapp-test-orchestrator/` и проверит наличие нужных MCPs.

### 2. MCP-серверы

```bash
claude mcp add --scope user playwright npx @playwright/mcp@latest
claude mcp add --scope user chrome-devtools npx chrome-devtools-mcp@latest
```

Без MCPs skill не запустится.

### 3. Перезапуск Claude Code

Skills загружаются на старте сессии — закрой Claude Code и открой заново.

### 4. Проверка

В Claude Code сказать «test the app» — должен активироваться `webapp-test-orchestrator` и показать таблицу `Project state` со статусом проекта.

---

## Использование в новом проекте

### Минимум — `.env.test` в корне проекта

```bash
TEST_BASE_URL=https://your-app.example.com
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=your-password
```

Optional:

```bash
TEST_API_LOGIN_PATH=/api/auth/login    # default
TEST_API_TOKEN_FIELD=access_token      # default — JSON-поле с JWT
```

`.env.test` автоматически добавляется в `.gitignore` skillом.

### Альтернатива — глобальный credentials file

```bash
export TEST_CREDENTIALS_FILE=~/.config/webtest-orch/credentials.env
```

В этом файле — секции для каждого проекта.

### Запустить тест

В Claude Code, в директории проекта:

> «test the app»

или

> «check the login flow on https://your-app.example.com»

Skill определит что делать (BOOTSTRAP / REPLAY / HYBRID) и пройдёт по checklist'у.

---

## Что получишь на выходе

После прогона — папка `reports/<run-id>/`:

```
reports/run-2026-04-28-1430/
├── index.html        # интерактивный HTML-отчёт (Playwright + наш wrapper)
├── report.md         # markdown-сводка (severity breakdown, top issues)
├── bugs.json         # нормализованный список багов (S0–S3, P0–P3)
├── diff.json         # new / regression / persisting / fixed bugs
├── screenshots/      # failure screenshots (НЕ инлайнятся в чат)
├── traces/           # Playwright traces для replay debugging
└── network/          # HAR files
```

Сами `*.spec.ts` тесты — в `tests/specs/` проекта, коммитятся в репо.

---

## Режимы работы

```
detect_state.py → JSON
  ├─ no tests/ + no playwright.config → BOOTSTRAP    (full first run, Playwright MCP exploration)
  ├─ tests/ + specs покрывают flow    → REPLAY        (npx playwright test, ~$0 LLM cost)
  └─ tests/ + новый flow              → HYBRID        (replay существующих + explore новых)
```

**BOOTSTRAP** — первый запуск. Skill scaffold'ит `playwright.config.ts`, `tests/auth.setup.ts`, `tests/fixtures/index.ts`, проводит API-login, исследует UI через ARIA snapshots, генерирует POMs и spec'ы.

**REPLAY** — повторный запуск, тесты уже есть. `npx playwright test`, без LLM-вызовов на browser actions. LLM используется только для триажа НОВЫХ багов и отсутствующих в кеше console messages.

**HYBRID** — есть тесты, но нужен новый flow. Replay существующего + exploratory loop на новый.

---

## Image-budget protection (важно)

**Проблема Claude Code:** есть отдельный лимит на inline images (~50–100 за сессию). Скриншоты Playwright MCP по умолчанию возвращаются inline — забивают этот лимит и ломают сессию через `/compact` даже при пустом text-контексте.

**Решение skill'а:** скриншоты НИКОГДА не возвращаются в parent чат. Все browser-операции дискатчатся через Task subagent. Subagent сжигает свой image budget, parent остаётся чист. Vision-классификация (если нужна) — nested subagent на ОДИН screenshot, возвращает текстовый verdict.

Это hard rule в SKILL.md. Если когда-нибудь увидишь что Claude вернул screenshot inline во время skill execution — это баг skill'а, сообщи.

---

## Troubleshooting

| Симптом | Что проверить |
|---|---|
| «Unknown skill: webapp-test-orchestrator» | `ls ~/.claude/skills/webapp-test-orchestrator/SKILL.md`. Если есть — Claude Code не подхватил, нужен полный рестарт CLI. |
| Skill активировался, но probes пустые | `python ~/.claude/skills/webapp-test-orchestrator/scripts/detect_state.py --human` руками — должен показать таблицу |
| `Isolation verified: no` в probes | Запустить Step 0 self-test (см. SKILL.md), либо вручную: `python scripts/_image_isolation_check.py --gen-fixtures` → диспатчить subagent → `--mark-verified` |
| Playwright MCP не работает | `claude mcp list` — должен показать `playwright: ✓ Connected` |
| `auth.setup.ts` падает на API-login | Проверь `TEST_API_LOGIN_PATH`, `TEST_API_TOKEN_FIELD` в `.env.test`. Skill потом сделает fallback на UI-login. |

---

## Структура skill (для разработчика skill'а)

```
~/.claude/skills/webapp-test-orchestrator/
├── SKILL.md                         # workflow для Claude (не редактировать без знания формата)
├── README.md                        # этот файл
├── install.sh                       # copy/symlink в ~/.claude/skills/
├── LICENSE.txt                      # MIT
├── .isolation-verified              # marker: image-budget contract OK
├── scripts/
│   ├── detect_state.py              # state probe → JSON
│   ├── with_server.py               # dev-server lifecycle
│   ├── _image_isolation_check.py    # image-budget self-test helper
│   ├── run_suite.py                 # (Day 2) wraps `playwright test`
│   ├── fingerprint_bugs.py          # (Day 2) bug dedup + run diff
│   ├── triage_console.py            # (Day 3) console noise filter
│   ├── visual_diff.py               # (Day 3) pixel diff + nested-subagent vision
│   └── generate_report.py           # (Day 4) markdown + html + bugs.json
├── reference/
│   ├── playwright-patterns.md       # locator priority, anti-flake
│   ├── auth-strategies.md           # (Day 2) API-login, JWT, storageState
│   ├── a11y-patterns.md             # (Day 3) axe + qualitative checks
│   ├── responsive-checklist.md      # (Day 3) viewports, touch targets
│   ├── console-noise-patterns.md    # (Day 3) ignore-list defaults
│   ├── stack-specific.md            # (Day 4) Next.js, FastAPI, TG WebApp, WS/SSE
│   └── reporting.md                 # (Day 4) JSON schema + tracker mappings
├── templates/
│   ├── playwright.config.ts.tmpl
│   ├── auth.setup.ts.tmpl
│   ├── fixture.ts.tmpl
│   ├── pom.ts.tmpl
│   └── spec.ts.tmpl
├── examples/
│   └── *.spec.ts                    # реальные сгенерированные артефакты
└── fixtures/iso-test/{a,b,c}.png    # для self-test
```

For development: clone the repo, edit files, then run `bash install.sh` to re-deploy into `~/.claude/skills/`.

---

## License

MIT. See [`LICENSE`](./LICENSE).

## Contributing

PRs welcome. See [`CONTRIBUTING.md`](./CONTRIBUTING.md). For OS-specific bug reports use the dedicated issue template.
