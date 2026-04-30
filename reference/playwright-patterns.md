# Playwright patterns reference

> Loaded on demand. Do not pre-read at session start.

The skill enforces these patterns when generating specs. If a generated spec
violates them, regenerate — do not commit.

## Locator priority (mandatory order)

1. **`getByRole`** with accessible name — e.g. `getByRole('button', { name: 'Sign in' })`. Survives redesigns, aligns with screen-reader UX.
2. **`getByLabel`**, **`getByPlaceholder`** — form fields. Prefer `getByLabel` (placeholder is a hint, not a label).
3. **`getByText`**, **`getByAltText`**, **`getByTitle`** — content-anchored, brittle to copy edits. Use sparingly.
4. **`getByTestId`** — when a11y semantics aren't available. Add `data-testid` to component code; don't generate `.locator('[data-testid="x"]')`.
5. **CSS / XPath** — last resort. Required: a `// reason:` comment explaining why the higher tiers don't work, scoped via `.filter()` or `.and()`.

```ts
// ✅ Good
await page.getByRole('button', { name: 'Place order' }).click();

// ✅ Acceptable when role unavailable
await page.getByTestId('checkout-cta').click();

// ❌ Generated specs must NOT do this without justification
await page.locator('div.cart-summary > div:nth-child(3) button').click();
```

## Web-first assertions (auto-retrying)

These poll automatically. Prefer them over manual loops or `waitForTimeout`.

| Use | Don't |
|---|---|
| `await expect(locator).toBeVisible()` | `if (await locator.isVisible())` |
| `await expect(locator).toHaveText('X')` | `expect(await locator.textContent()).toBe('X')` |
| `await expect(page).toHaveURL(/\/dashboard/)` | `expect(page.url()).toMatch(/\/dashboard/)` |
| `await expect(locator).toBeEnabled()` | `await page.waitForTimeout(500)` |

`expect(locator).toBeVisible()` waits up to the test/expect timeout; `locator.isVisible()` returns immediately and is non-retrying — correct for branching, wrong for assertions.

## Tabs vs buttons (common a11y miss)

Many SPAs (Tailwind / headless-UI / radix without `Tabs` primitive) render
visual tab UIs using `<button>` elements WITHOUT `role="tab"`. Result:

```ts
// FAILS — locator returns 0 elements because there is no role=tab anywhere
await page.getByRole('tab', { name: /Free Chat/i }).click();
```

When ARIA snapshot during exploration shows the element as `button [ref=eN]`
but the visual treatment is a tab strip, generate the spec with
`getByRole('button', ...)` AND log the missing `role="tab"` as a soft a11y
finding:

```ts
issues.push(`a11y[moderate] aria-tabs: visual tab strip uses <button> without role="tab"`);
```

This way the test passes (button locator works) and the a11y bug is recorded
(screen-reader users can't navigate the tabs as a tablist).

## Anti-flake patterns

- **Listeners attach BEFORE `page.goto()`** — `page.on('console', ...)` registered after navigation misses early errors.
- **No `waitForTimeout`** — replaced by web-first assertions or `waitForResponse`/`waitForLoadState`.
- **No `nth(0)` / `first()` / `last()` without scoping** — use `.filter({ hasText: 'X' })` to narrow first.
- **No UI login per test** — use `storageState` setup project (see auth-strategies).
- **No one-mega-test** — one flow per `test()`; one flow per file when the flow is non-trivial.
- **No hardcoded waits for animations** — use `await page.waitForFunction(() => ...)` polling a stable signal.
- **Network responses for state changes** — `await page.waitForResponse(/api\/orders/)` after a click that posts.
- **Don't assert immediately after navigation** — `await page.waitForURL(...)` first; `expect(page).toHaveURL` is the same with retry built-in.

## Test structure (POM + Fixtures)

```
tests/
├── pages/                  # POMs
│   ├── LoginPage.ts
│   └── DashboardPage.ts
├── fixtures/
│   └── index.ts            # test.extend with POMs
├── helpers/
│   ├── api-login.ts
│   └── otp.ts
├── specs/
│   ├── auth-login.spec.ts
│   └── checkout-place-order.spec.ts
└── auth.setup.ts           # writes playwright/.auth/user.json once
```

Fixture pattern keeps specs short:

```ts
// tests/fixtures/index.ts
import { test as base } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { DashboardPage } from '../pages/DashboardPage';

export const test = base.extend<{ loginPage: LoginPage; dashboardPage: DashboardPage }>({
  loginPage: async ({ page }, use) => use(new LoginPage(page)),
  dashboardPage: async ({ page }, use) => use(new DashboardPage(page)),
});
export { expect } from '@playwright/test';

// tests/specs/auth-login.spec.ts
import { test, expect } from '../fixtures';

test('user can sign in', async ({ loginPage, dashboardPage }) => {
  await loginPage.goto();
  await loginPage.signIn(process.env.TEST_USER_EMAIL!, process.env.TEST_USER_PASSWORD!);
  await expect(dashboardPage.userMenu).toBeVisible();
});
```

## Console + network listening (in spec, not in helper)

Listeners are per-test for isolation:

```ts
test('does not error during signup', async ({ page }) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];

  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(`console: ${m.text()}`);
  });
  page.on('response', (r) => {
    if (r.status() >= 400) failedRequests.push(`${r.status()} ${r.url()}`);
  });
  page.on('requestfailed', (r) => failedRequests.push(`fail ${r.url()} ${r.failure()?.errorText}`));

  // ... test body ...

  // HTTP 4xx/5xx do NOT fire requestfailed — listen on response too.
  expect.soft(consoleErrors, 'console errors').toEqual([]);
  expect.soft(failedRequests, 'failed requests').toEqual([]);
});
```

`expect.soft` lets the test continue and report all listener violations together.

## Projects + viewports

`playwright.config.ts` projects (skill default):

| Project name | Browser | Viewport | Use |
|---|---|---|---|
| `chromium-desktop` | Chromium | 1920×1080 | Primary desktop coverage |
| `chromium-laptop` | Chromium | 1366×768 | Catches mid-size layout breaks |
| `chromium-mobile` | Chromium | 390×844 (iPhone 13) | Mobile-Chrome surrogate |
| `pixel5` | Chromium | 393×851 (Pixel 5) | Android-Chrome layout edge cases |
| `mobile-safari` | WebKit | 390×844 | Telegram in-app browser, iOS Safari |

Run a subset: `npx playwright test --project=chromium-desktop`.

## Generated spec template

```ts
// tests/specs/<feature>.spec.ts
import { test, expect } from '../fixtures';
import AxeBuilder from '@axe-core/playwright';

test.describe('<feature> — <short scope>', () => {
  test('<scenario>', async ({ page, loginPage }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (e) => consoleErrors.push(e.message));
    page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()));

    await loginPage.goto();
    await expect(page).toHaveTitle(/<expected fragment>/);

    const a11y = await new AxeBuilder({ page }).withTags(['wcag22aa']).analyze();
    expect.soft(a11y.violations, 'a11y on landing').toEqual([]);

    // ... interaction body ...

    expect(consoleErrors, 'no uncaught errors').toEqual([]);
  });
});
```

## Healing policy

**webtest-orch does NOT ship self-healing.** This is intentional, not a gap.
The QA community in 2026 has begun pushing back on self-healing as marketing
spin — the failure mode is well-documented: a healer picks a visually-similar-
but-wrong element ("Pay now" → wrong button), the test goes green, and the bug
ships. Engineers stop trusting suites that *lie*. We prefer red over false-green.

If you want native Playwright self-healing, it's free and opt-in — Microsoft
ships **Test Agents** (`npx playwright init-agents --loop=claude`) with a built-
in Healer. webtest-orch is compatible. **Recommended policy** when you enable it:

- Healer **may patch locators** only when the patched test still exercises the
  same intent (same accessible name, same role).
- For UI behaviour changes (button does nothing now, form submits but doesn't
  validate), Healer must mark the test `test.skip` and emit a bug record — it
  does NOT silently adapt.

Adapt only what's accidental; surface what's substantive. Silent healing
is how a regression ships in green CI.
