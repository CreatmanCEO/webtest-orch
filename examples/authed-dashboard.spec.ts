// Example: authenticated dashboard test. Demonstrates POM + fixtures pattern,
// API-login via auth.setup.ts (storageState reused — no UI login per test),
// and per-test listeners.
//
// Prerequisites:
//   tests/auth.setup.ts    — runs once, writes playwright/.auth/user.json
//   tests/fixtures/index.ts — extends base test with DashboardPage POM
//   tests/pages/DashboardPage.ts — page-object class
//
// playwright.config.ts has setup project + storageState pointing here.

import { test, expect } from '../fixtures';
import AxeBuilder from '@axe-core/playwright';

test.describe('Authed Dashboard', () => {
  test('user lands on dashboard after auth, primary widgets render', async ({
    page,
    dashboardPage,
  }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];
    const issues: string[] = [];

    page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(`console: ${m.text()}`);
    });
    page.on('response', (r) => {
      if (r.status() >= 400 && !/\/(favicon|robots|sw\.js)/.test(r.url())) {
        failedRequests.push(`${r.status()} ${r.url()}`);
      }
    });

    await dashboardPage.goto();

    // Sanity: storageState got us in. NOT redirected to /login.
    await expect(page).not.toHaveURL(/\/(login|signin|auth)\b/);

    // Primary widgets — adjust selectors to your app's actual roles.
    await expect(page.getByRole('navigation')).toBeVisible();
    await expect(page.getByRole('main')).toBeVisible();
    await expect(dashboardPage.userMenu).toBeVisible();

    // Axe scan only on authed view (different DOM than public landing).
    const a11y = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .exclude('[data-recharts]') // ignore charting library widgets
      .analyze();
    a11y.violations.forEach((v) => {
      issues.push(`a11y[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}x nodes)`);
    });

    // Hard fail with full picture.
    expect(
      issues,
      issues.length > 0 ? `${issues.length} issues found:\n  - ${issues.join('\n  - ')}` : '',
    ).toEqual([]);
    expect(consoleErrors, 'no uncaught console errors').toEqual([]);
    expect(failedRequests, 'no 4xx/5xx or net failures').toEqual([]);
  });
});
