import { expect, test } from '@playwright/test';

const password = 'Password123';

test.describe('core browser flow', () => {
  test('registers, creates a course, and preserves local auth errors', async ({ page }) => {
    const email = `browser-${Date.now()}@example.com`;

    await page.goto('/auth/register');
    await expect(page.getByRole('heading', { name: /create your account/i })).toBeVisible();
    await page.locator('#full_name').fill('Browser Student');
    await page.locator('#email').fill(email);
    await page.locator('#password').fill(password);
    await page.locator('#confirm_password').fill(password);
    await page.getByRole('button', { name: /create account/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();

    await page.getByRole('button', { name: /create course/i }).click();
    await page.getByPlaceholder('e.g., Introduction to Machine Learning').fill('Browser E2E Biology');
    await page.getByPlaceholder('e.g., Dr. Smith').fill('Dr. Browser');
    await page.getByPlaceholder('e.g., Computer Science, Biology').fill('Biology');
    await page.locator('form').getByRole('button', { name: /^create course$/i }).click();

    await expect(page.getByText('Browser E2E Biology')).toBeVisible();

    await page.goto('/dashboard/settings');
    await page.locator('#current_password').fill('wrong-password');
    await page.locator('#new_password').fill('NewPassword123');
    await page.locator('#confirm_password').fill('NewPassword123');
    await page.getByRole('button', { name: /change password/i }).click();

    await expect(page.getByText(/current password is incorrect/i)).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard\/settings/);
  });
});
