# Authentication strategies reference

> Loaded on demand. Day 2.

The skill prefers **API-based login** over UI-driven login because API login is fast, deterministic, and bypasses bot-detection layers. UI login is fallback only.

## Setup project pattern

`playwright.config.ts` defines a `setup` project that runs `tests/auth.setup.ts` once before any other project. The setup writes `playwright/.auth/user.json` with cookies + localStorage. All other projects load it via `storageState: 'playwright/.auth/user.json'` and depend on setup via `dependencies: ['setup']`.

This means **every test runs already authenticated** without re-doing the login flow per test — saves time and reduces flake.

## Pattern 1 — API login + JWT (preferred)

For FastAPI, Express, NestJS, Django REST — backends with `/api/auth/login` returning JWT.

```ts
const response = await request.post(`${baseURL}/api/auth/login`, {
  data: { email: process.env.TEST_USER_EMAIL, password: process.env.TEST_USER_PASSWORD },
});
const { access_token } = await response.json();

await page.goto(baseURL);
await page.evaluate((tk) => {
  localStorage.setItem('access_token', tk);
}, access_token);
await page.context().storageState({ path: 'playwright/.auth/user.json' });
```

If JWT lives in HttpOnly cookies, `request.post()` captures them automatically and `storageState` persists them.

## Pattern 2 — UI login (fallback)

Use only when no API endpoint exists. The `auth.setup.ts.tmpl` template tries Pattern 1 first, falls back to Pattern 2 automatically.

```ts
await page.goto(`${baseURL}/login`);
await page.getByLabel(/email/i).fill(email);
await page.getByLabel(/password/i).fill(password);
await page.getByRole('button', { name: /sign ?in|войти/i }).click();
await expect(page).not.toHaveURL(/\/login/);
await page.context().storageState({ path: 'playwright/.auth/user.json' });
```

UI login is brittle to copy edits, slower, and triggers bot detection. **Recommend any project to expose a test-only API login endpoint** to remove this risk.

## Pattern 3 — Token via env (server-issued)

Some apps issue test tokens server-side (admin panels with bot tokens, machine-to-machine auth). Inject directly:

```ts
await page.goto(baseURL);
await page.evaluate((tk) => {
  localStorage.setItem('admin_token', tk);
}, process.env.TEST_ADMIN_TOKEN);
await page.context().storageState({ path: 'playwright/.auth/user.json' });
```

For Telegram WebApps — see `stack-specific.md` (Day 4).

## Pattern 4 — OAuth / magic links (advanced)

These flows have anti-automation defences (PKCE, magic-link emails, MFA). Vanilla Playwright handles them poorly. Options:

1. **Bypass via API.** Most OAuth providers issue test tokens for the `client_credentials` grant; use that path instead of the UI dance.
2. **Email-magic-link.** Programmatically read inbox via Mailpit / Mailtrap / a temp inbox API. Not bundled — document per project.
3. **Stagehand v3.** `observe()` / `act()` for resilient handling. Driver-agnostic since v3, MIT. Not bundled with this skill — install separately if needed.

If a project requires OAuth and none of these work — file an issue, it's a v2 feature.

## Re-authentication

When `playwright/.auth/user.json` expires (JWT timeout, server-side rotation, password change):

1. Run `npx playwright test --project=setup` — re-runs `auth.setup.ts`, refreshes the file.
2. The skill detects this case via `detect_state.py` (`auth.stateFile: present` AND `auth.stateAge > 12h`) — adds a refresh step in the workflow.

If failures look like 401/403 storms, the auth file is the first thing to refresh.

## Required environment variables

```
TEST_BASE_URL              # required — e.g. https://your-app.example.com
TEST_USER_EMAIL            # required
TEST_USER_PASSWORD         # required
TEST_API_LOGIN_PATH        # optional — default /api/auth/login
TEST_API_TOKEN_FIELD       # optional — default access_token (also tried: token, jwt)
TEST_ADMIN_TOKEN           # optional — for Pattern 3
TEST_USER_AGENT_KIND       # optional — desktop|mobile|telegram, default desktop
```

Read order in skill (first hit wins):

1. `<project>/.env.test`
2. `${TEST_CREDENTIALS_FILE}` env var → global file
3. Skill prompts user once, writes to `<project>/.env.test`, adds `.env.test` to `.gitignore`

## Anti-pattern: credentials inline in spec files

❌

```ts
test('logs in', async ({ page }) => {
  await page.getByLabel(/email/i).fill('test@example.com');
  await page.getByLabel(/password/i).fill('hunter2');  // committed to git!
});
```

✅

```ts
test('logs in', async ({ page }) => {
  await page.getByLabel(/email/i).fill(process.env.TEST_USER_EMAIL!);
  await page.getByLabel(/password/i).fill(process.env.TEST_USER_PASSWORD!);
});
```

The skill enforces this in generated specs. Hand-edits must follow the same rule.
