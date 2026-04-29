# A11y patterns reference

> Loaded on demand. Day 3.

Two layers: **deterministic** (axe-core finds ~57% of WCAG issues) + **qualitative** (LLM contextual review for the other ~43% — alt-text relevance, layout sanity, screen-reader UX).

## Layer 1 — axe-core (deterministic)

Every generated spec includes an axe scan with WCAG 2.2 AA tags:

```ts
import AxeBuilder from '@axe-core/playwright';

const a11y = await new AxeBuilder({ page })
  .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
  .exclude('[id^="google_ads_iframe_"]')   // 3rd-party noise
  .exclude('iframe[src*="youtube.com"]')   // 3rd-party noise
  .analyze();

expect.soft(a11y.violations, 'a11y violations on this page').toEqual([]);
```

**`expect.soft`** lets the test continue and report all listener results together — vs `expect` which stops on first failure.

WCAG 3.0 stays a Working Draft (March 2026 update). Don't fail builds on it. APCA contrast can be tracked as an early signal but not as an enforce-rule.

## Layer 2 — qualitative checks (LLM via nested subagent)

These need judgement, not rules:

| Check | Deterministic part | LLM part |
|---|---|---|
| Alt-text relevance | axe checks PRESENCE | LLM compares image content to alt string |
| Heading hierarchy | DOM scrape `<h1>..<h6>` | LLM validates semantic order |
| Focus order | Tab-key crawl returns selector path | LLM judges if order matches reading flow |
| Modal focus traps | `expect(dialog.locator(':focus')).toBeVisible()` | — (deterministic enough) |
| Toast aria-live | `expect(toast).toHaveAttribute('aria-live', /polite\|assertive/)` | — |
| Custom widget ARIA | axe checks role validity | LLM validates against APG |

### Alt-text relevance — Pattern B (vision)

For images with `alt` attributes, dispatch ONE Task subagent per suspect image:

```
Subagent prompt:
"Read this image: <abs path>. Compare to its alt text: '<alt>'.
 Output ONE line: 'OK' if alt is relevant, or 'BAD: <reason>' otherwise."
```

Skill enforces image-budget protection: parent never receives the image.

### Heading hierarchy — text-only

```ts
const headings = await page.locator('h1, h2, h3, h4, h5, h6').evaluateAll(
  (els) => els.map((e) => ({ level: parseInt(e.tagName[1]), text: e.textContent?.trim() })),
);
// Check for jumps: h1 → h3 (skipped h2)
for (let i = 1; i < headings.length; i++) {
  const jump = headings[i].level - headings[i - 1].level;
  expect.soft(jump, `heading jump at ${headings[i].text}`).toBeLessThanOrEqual(1);
}
```

### Focus order — Tab-key crawl

```ts
async function tabCrawl(page) {
  const focused: string[] = [];
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press('Tab');
    const sel = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      return el.getAttribute('aria-label') || el.textContent?.slice(0, 40) || el.tagName;
    });
    if (!sel) break;
    focused.push(sel);
  }
  return focused;
}
```

Compare focus order to expected reading flow — pure text, no images.

## Touch targets (WCAG 2.5.8 AA — 24×24 CSS px)

```ts
test('all interactive elements meet 24×24 touch target', async ({ page }) => {
  const tooSmall = await page.locator('button, a, input').evaluateAll((els) =>
    els
      .filter((e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24);
      })
      .map((e) => ({
        tag: e.tagName,
        text: e.textContent?.slice(0, 30),
        size: `${e.getBoundingClientRect().width}×${e.getBoundingClientRect().height}`,
      })),
  );
  expect.soft(tooSmall, 'touch targets below 24×24').toEqual([]);
});
```

AAA target is 44×44 — track but don't fail on it.

## Color contrast — defer to axe-core

axe handles WCAG 1.4.3 AA (4.5:1 normal, 3:1 large) and 1.4.6 AAA (7:1, 4.5:1). APCA is the future contrast model — tools exist (axe-core has `apca-contrast` rule disabled by default) but not stable enough to fail builds yet.

## Modal focus traps

```ts
test('modal traps focus', async ({ page }) => {
  await page.getByRole('button', { name: /open/i }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  // Tab forward — should stay inside dialog
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press('Tab');
    const insideDialog = await dialog.evaluate((d) => d.contains(document.activeElement));
    expect(insideDialog).toBe(true);
  }
});
```

## Toast / live region announcements

```ts
const toast = page.getByRole('status').or(page.getByRole('alert'));
await expect(toast).toBeVisible();
await expect(toast).toHaveAttribute('aria-live', /polite|assertive/);
```

## Skip links

A11y nicety — `<a href="#main">Skip to content</a>` should appear first in tab order. Test:

```ts
await page.keyboard.press('Tab');
const first = await page.evaluate(() => document.activeElement?.textContent);
expect(first).toMatch(/skip to|перейти к/i);
```

## Image-budget protection on a11y workflows

When delegating qualitative a11y checks to a Task subagent — ALWAYS use Pattern B from SKILL.md (one image, text verdict). Never iterate over many images in the parent context.

For batch checks (e.g. all images on the page), spawn one subagent per image OR have the subagent use Glob + Read inside its own context, return a single text summary.
