import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Color contrast accessibility', () => {

  test('home page has no contrast violations', async ({ page }, testInfo) => {
    await page.goto('/');
    await page.waitForSelector('#app');
    // Wait for CSS color transitions to complete (body has 0.5s transition)
    await page.waitForTimeout(600);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2aa'])
      .analyze();

    const contrastViolations = results.violations.filter(
      v => v.id === 'color-contrast'
    );

    // Attach details to report for debugging
    await testInfo.attach('contrast-violations', {
      body: JSON.stringify(contrastViolations, null, 2),
      contentType: 'application/json',
    });

    expect(contrastViolations).toEqual([]);
  });
});

// Specific test targeting the known banner issue
test.describe('Update Banner', () => {
  test('should have sufficient contrast', async ({ page }) => {
    await page.goto('/');
    // Wait for CSS color transitions to complete
    await page.waitForTimeout(600);

    const banner = page.locator('.update-banner');
    if (await banner.isVisible()) {
      const results = await new AxeBuilder({ page })
        .include('.update-banner')
        .analyze();

      const issues = results.violations.filter(v => v.id === 'color-contrast');
      expect(issues).toEqual([]);
    }
  });
});
