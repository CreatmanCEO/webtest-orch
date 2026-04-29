# Responsive checklist

> Loaded on demand. Day 3.

## Viewports the skill tests by default

| Project | Browser | Viewport | Why |
|---|---|---|---|
| `chromium-desktop` | Chromium | 1920×1080 | Most common desktop FullHD |
| `chromium-laptop` | Chromium | 1366×768 | Mid-size laptop — many UX bugs hide here |
| `chromium-mobile` | Chromium / iPhone 13 device | 390×844 | Mobile Chrome surrogate |
| `pixel5` | Chromium / Pixel 5 device | 393×851 | Catches Android-specific layout |
| `mobile-safari` | WebKit / iPhone 13 device | 390×844 | iOS Safari + Telegram in-app browser |

Run a single project: `npx playwright test --project=chromium-mobile`.
Run all: omit `--project` (or pass `--project=all`).

## Touch target sizes

WCAG 2.5.8 (AA, 2.2 spec) — interactive elements ≥ 24×24 CSS px.
WCAG 2.5.5 (AAA) — ≥ 44×44 CSS px.

The skill enforces AA in generated specs. AAA is a soft warning.

## Common responsive bugs the skill catches

1. **Horizontal overflow** — content wider than viewport:
    ```ts
    const overflows = await page.evaluate(() =>
      document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect.soft(overflows, 'no horizontal overflow').toBe(false);
    ```

2. **Touch target too small** — see `a11y-patterns.md` snippet.

3. **Fixed-width hardcodes** — search for `width: \d+px` in computed styles for top-level layout containers; these often break < 768px.

4. **Off-screen menus** — mobile burger menu position when open:
    ```ts
    await page.getByRole('button', { name: /menu|open menu/i }).click();
    const menu = page.getByRole('navigation');
    const box = await menu.boundingBox();
    expect.soft(box?.x, 'menu visible on screen').toBeGreaterThanOrEqual(0);
    expect.soft(box?.x + (box?.width ?? 0), 'menu fits viewport').toBeLessThanOrEqual(390);
    ```

5. **Safe area insets (iOS notch)** — bottom navigation must respect `env(safe-area-inset-bottom)`:
    ```ts
    const tabBar = page.locator('[data-mobile-tab-bar]');
    const padBottom = await tabBar.evaluate((el) =>
      getComputedStyle(el).paddingBottom
    );
    expect.soft(padBottom, 'safe-area padding present').toMatch(/env\(safe-area|^\d+px$/);
    ```

6. **Tap delay / touch-action** — buttons need `touch-action: manipulation` to avoid 300ms delay on iOS:
    ```ts
    const taTouch = await page.evaluate(() => {
      const btn = document.querySelector('button');
      return btn ? getComputedStyle(btn).touchAction : null;
    });
    expect.soft(taTouch, 'touch-action set').toBe('manipulation');
    ```

## Image-budget protection on responsive checks

For **layout sanity** (zero-baseline, first run), don't ask Claude to look at multiple screenshots. Use:

- DOM scrape (`scrollWidth`, `clientWidth`, computed styles) → text → assertions in spec
- Pixel-diff (`toHaveScreenshot()`) for known baselines → diff% as text → vision Pattern B only when diff fires

Vision is a last resort, not a default sweep.

## Anti-patterns

- ❌ `await page.setViewportSize({ width: ..., height: ... })` mid-test — use Playwright projects, one viewport per project
- ❌ One mega-test that loops viewports — use `test.describe.parallel` with project-level matrix
- ❌ Hardcoded pixel values in assertions (e.g. `expect(box.width).toBe(390)`) — assert ranges or proportions
- ❌ Skipping mobile-safari "because we're Chrome-only" — Telegram, iOS users matter
- ❌ Running `toHaveScreenshot()` without a `mask` for dynamic content — flake guaranteed (clocks, ads, animations)

## Mask dynamic content for stable screenshots

```ts
await expect(page).toHaveScreenshot({
  mask: [
    page.locator('[data-current-time]'),
    page.locator('iframe[src*="ads"]'),
    page.locator('.user-avatar'),  // changes per-session
  ],
  maxDiffPixelRatio: 0.001,        // 0.1% tolerance for AA jitter
});
```
