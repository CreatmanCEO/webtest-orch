import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Demo CI smoke', () => {
  test('demo home baseline — expects to fail with planted bugs', async ({ page }) => {
    const consoleErrors: string[] = [];
    const issues: string[] = [];

    page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(`console: ${m.text()}`);
    });

    await page.goto('/');

    const a11y = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();
    a11y.violations.forEach((v) =>
      issues.push(`a11y[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}x nodes)`)
    );

    const headings = await page.locator('h1,h2,h3,h4,h5,h6').evaluateAll(
      (els) => els.map((e) => ({
        level: parseInt(e.tagName[1]),
        text: (e.textContent || '').trim().slice(0, 40),
      }))
    );
    for (let i = 1; i < headings.length; i++) {
      if (headings[i].level - headings[i - 1].level > 1) {
        issues.push(`heading-jump: h${headings[i - 1].level}->h${headings[i].level} at "${headings[i].text}"`);
      }
    }

    const tooSmall = await page.locator('a, button, input, [role="button"]').evaluateAll((els) =>
      els
        .filter((e: Element) => {
          const r = (e as HTMLElement).getBoundingClientRect();
          return r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24);
        })
        .map((e: Element) => {
          const el = e as HTMLElement;
          const r = el.getBoundingClientRect();
          const text = (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 25);
          return `${el.tagName}:"${text}" ${Math.round(r.width)}x${Math.round(r.height)}`;
        })
    );
    tooSmall.forEach((t) => issues.push(`touch-target: ${t} (WCAG 2.5.8 needs 24x24)`));

    expect(
      issues,
      issues.length > 0 ? `${issues.length} issues found:\n  - ${issues.join('\n  - ')}` : '',
    ).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
