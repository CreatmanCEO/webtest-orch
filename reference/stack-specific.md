# Stack-specific guidance

> Loaded on demand. Day 4. Use the section that matches the project under test.

## Next.js (Pages Router or App Router)

- **Hydration mismatches** are real bugs, NOT noise — keep `Hydration failed` and `Text content does not match` in the bug list (skill default).
- **Test against deployed previews** when possible (Cloudflare Pages, Vercel preview URLs) — catches CDN / edge-runtime quirks Node compat misses.
- **Local dev server**: configure `webServer` in `playwright.config.ts`:
    ```ts
    webServer: {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    ```
- **App Router cookies/auth**: `request.post()` cookies persist via `storageState` — works the same as Pages Router.
- **`next-auth` JWT** lives in `next-auth.session-token` cookie (HttpOnly). API login automatically captures it.

## FastAPI + JWT

Common pattern across the Python web ecosystem. Auth setup:

```ts
// auth.setup.ts already does this; documented for tweaks
const r = await request.post(`${baseURL}/api/auth/login`, {
  data: { email: process.env.TEST_USER_EMAIL, password: process.env.TEST_USER_PASSWORD },
});
const { access_token } = await r.json();
```

If FastAPI sets the JWT in a cookie (with `set_cookie()`), `request.post()` captures it automatically. If it returns the token in body and the front-end puts it in `localStorage`, the spec injects it via `page.evaluate(...)` (see `auth-strategies.md` Pattern 1).

**FastAPI 422 unprocessable entity on login** — the request body shape is wrong. Check actual `/docs` schema; sometimes it's `{"username": ..., "password": ...}` (OAuth2 password flow), sometimes `{"email": ..., "password": ...}`. Override via `TEST_API_LOGIN_PATH` if path differs.

## Telegram WebApp (mini apps)

WebApp's runtime is the **Telegram in-app browser = WebKit**. Test through `mobile-safari` Playwright project.

`window.Telegram.WebApp.initDataUnsafe` doesn't exist outside Telegram. Mock it via `addInitScript` BEFORE navigation:

```ts
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).Telegram = {
      WebApp: {
        initData: 'mock_init_data',
        initDataUnsafe: {
          user: { id: 123, first_name: 'Test', username: 'test' },
          auth_date: Math.floor(Date.now() / 1000),
          hash: 'mock_hash',
        },
        ready: () => {},
        expand: () => {},
        close: () => {},
        MainButton: { setText: () => {}, show: () => {}, hide: () => {}, onClick: () => {} },
        BackButton: { show: () => {}, hide: () => {}, onClick: () => {} },
      },
    };
  });
});
```

For admin panels with bot-token auth: store the bot token in `.env.test` and inject via `localStorage` in `auth.setup.ts` (Pattern 3 in `auth-strategies.md`).

## WebSocket / SSE flows (real-time chat, voice)

Listen on `page.on('websocket')`:

```ts
const wsLog: string[] = [];
page.on('websocket', (ws) => {
  ws.on('framesent', (e) => wsLog.push(`→ ${e.payload.toString().slice(0, 100)}`));
  ws.on('framereceived', (e) => wsLog.push(`← ${e.payload.toString().slice(0, 100)}`));
  ws.on('close', () => wsLog.push('WS closed'));
});
```

**Don't fail on connection-close events during navigation** — they're normal. Filter in assertions:

```ts
const realErrors = wsLog.filter(l => !l.includes('WS closed'));
expect(realErrors.length).toBeGreaterThan(0); // we expected some traffic
```

SSE responses come through normally on `page.on('response')` — check `content-type: text/event-stream`.

## TTS / STT (canvas, Web Audio API)

Often render to `<canvas>` waveforms or use Web Audio. The a11y tree won't expose them. Two strategies:

1. **Behavioral assertions** — button state changes, network requests to TTS provider, `audio.duration > 0`:
    ```ts
    const audio = page.locator('audio').first();
    await expect(audio).toHaveJSProperty('duration', expect.any(Number));
    ```
2. **Mock external TTS** for deterministic CI:
    ```ts
    await page.route('**/api.elevenlabs.io/**', route => route.fulfill({
      status: 200,
      contentType: 'audio/mpeg',
      body: Buffer.from('mock-mp3-bytes'),
    }));
    ```

**Image-budget caveat**: do NOT call `browser_take_screenshot` on a canvas waveform from the parent context. If you need to verify visual output, use Pattern B (Task subagent reads ONE screenshot, returns text verdict).

## Cloudflare Pages / Workers / Coolify

- **Edge-runtime quirks** — Cloudflare Workers Node compat is incomplete for some libraries (Buffer, fs, child_process). Test against the deployed preview to catch these.
- **Coolify Docker builds** — webServer config can spawn `docker compose up` if needed; usually easier to test against the deployed URL.
- **Cache invalidation** — production tests after a deploy might hit stale cache for ~30s. Add a `await page.waitForResponse(r => r.url().includes('/api/health'))` before assertions to confirm fresh deploy.

## Drizzle / Prisma migrations

Schema migrations can break unit tests but rarely surface in e2e. If they do — DB seed in setup project:

```ts
// tests/setup/db-seed.ts
setup('seed db', async () => {
  await execAsync('npm run db:seed:test');
});
```

## Per-project credential isolation (multi-app setups)

When testing many apps from one machine, the recommended layout is one shared
credentials file with sections per app, plus a project-scoped `.env.test` that
points at the shared file:

```
~/.config/webtest-orch/credentials.env

# App A
APP_A_TEST_USER=qa@example.com
APP_A_TEST_PASS=...

# App B (public site — no creds needed)

# App C (Telegram admin)
APP_C_ADMIN_TOKEN=...
```

In each project's `.env.test`:

```
TEST_BASE_URL=https://app-a.example.com
TEST_USER_EMAIL=${APP_A_TEST_USER}
TEST_USER_PASSWORD=${APP_A_TEST_PASS}
```

`dotenv` does NOT expand `${VAR}` references by default. Use `dotenv-expand` or
write absolute values per project.

Alternative: set `TEST_CREDENTIALS_FILE=~/.config/webtest-orch/credentials.env` —
skill reads this if `<project>/.env.test` is missing the required keys.
