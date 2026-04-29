// Example: Telegram WebApp / Mini-app testing.
//
// Telegram in-app browser is WebKit. Run this spec under the `mobile-safari`
// project from playwright.config.ts.
//
// `window.Telegram.WebApp.initDataUnsafe` doesn't exist outside Telegram —
// we mock it via addInitScript BEFORE navigation so the app's auth code
// thinks it's running inside Telegram.

import { test, expect } from '@playwright/test';

test.describe('Telegram WebApp Mini-app', () => {
  test.beforeEach(async ({ page }) => {
    // Mock Telegram WebApp SDK. Adjust the user object to match your app's
    // expected fields (most apps read `user.id`, `user.first_name`, `user.username`).
    await page.addInitScript(() => {
      (window as any).Telegram = {
        WebApp: {
          initData: 'mock_init_data',
          initDataUnsafe: {
            user: { id: 123456789, first_name: 'Test', username: 'qa_bot', language_code: 'en' },
            auth_date: Math.floor(Date.now() / 1000),
            hash: 'mock_hash_for_testing',
            chat_type: 'private',
          },
          version: '7.0',
          platform: 'web',
          colorScheme: 'light',
          ready: () => {},
          expand: () => {},
          close: () => {},
          MainButton: {
            text: '',
            isVisible: false,
            setText: function (t: string) { this.text = t; },
            show: function () { this.isVisible = true; },
            hide: function () { this.isVisible = false; },
            onClick: () => {},
            offClick: () => {},
          },
          BackButton: {
            isVisible: false,
            show: function () { this.isVisible = true; },
            hide: function () { this.isVisible = false; },
            onClick: () => {},
          },
          HapticFeedback: {
            impactOccurred: () => {},
            notificationOccurred: () => {},
          },
        },
      };
    });
  });

  test('mini-app loads with mocked Telegram context', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(`console: ${m.text()}`);
    });

    await page.goto('/');

    // The app should NOT redirect to a "open in Telegram" warning page —
    // our mock convinced it that we're inside Telegram.
    await expect(page).not.toHaveURL(/\/(open-in-telegram|tg-only)/);

    // The app reads user from the mocked SDK and renders something with the name.
    await expect(page.getByText(/Test|qa_bot/)).toBeVisible({ timeout: 10_000 });

    expect(consoleErrors, 'no uncaught errors').toEqual([]);
  });
});
