import { expect, test, type Page } from '@playwright/test';

const password = 'Password123';
const studyMaterial = Buffer.from(
  [
    'Browser full flow biology lecture.',
    'Photosynthesis, cellular respiration, mitosis, meiosis, and experimental evidence appear repeatedly in the course materials.',
    'Exam questions emphasize theoretical frameworks, practical applications, quantitative methods, and critical analysis.',
  ].join('\n'),
  'utf-8'
);

async function registerAndCreateCourse(page: Page, courseName: string) {
  const email = `browser-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;

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
  await page.getByPlaceholder('e.g., Introduction to Machine Learning').fill(courseName);
  await page.getByPlaceholder('e.g., Dr. Smith').fill('Dr. Browser');
  await page.getByPlaceholder('e.g., Computer Science, Biology').fill('Biology');
  await page.locator('form').getByRole('button', { name: /^create course$/i }).click();

  await expect(page.getByText(courseName)).toBeVisible();
  await page.getByRole('link', { name: /open/i }).click();
  await expect(page.getByRole('heading', { name: courseName })).toBeVisible();
}

async function answerEveryQuestion(page: Page) {
  const radioNames = await page.locator('input[type="radio"]').evaluateAll((inputs) =>
    Array.from(new Set(inputs.map((input) => (input as HTMLInputElement).name)))
  );
  for (const name of radioNames) {
    await page.locator(`input[type="radio"][name="${name}"]`).first().check({ force: true });
  }

  const textInputs = page.locator('input[type="text"]');
  const textInputCount = await textInputs.count();
  for (let i = 0; i < textInputCount; i += 1) {
    await textInputs.nth(i).fill('Effective output is 200 units and deviation is 20 percent.');
  }

  const textareas = page.locator('textarea');
  const textareaCount = await textareas.count();
  for (let i = 0; i < textareaCount; i += 1) {
    await textareas.nth(i).fill(
      'A strong answer discusses the theoretical basis, practical applications, known limitations, and current research directions.'
    );
  }
}

test.describe('core browser flow', () => {
  test('registers, creates a course, and preserves local auth errors', async ({ page }) => {
    await registerAndCreateCourse(page, 'Browser E2E Biology');
    await page.getByRole('button', { name: /upload files/i }).click();
    await page.locator('input[type="file"]').setInputFiles({
      name: 'legacy-notes.doc',
      mimeType: 'application/msword',
      buffer: Buffer.from('legacy doc'),
    });
    await expect(page.getByText(/legacy \.doc files are not supported/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /^upload$/i })).toBeDisabled();
    await page.getByRole('button', { name: /clear all/i }).click();

    await page.locator('input[type="file"]').setInputFiles({
      name: 'misleading.pdf',
      mimeType: 'image/png',
      buffer: Buffer.from('not a pdf'),
    });
    await expect(page.getByText(/does not match the \.pdf extension/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /^upload$/i })).toBeDisabled();
    await page.getByRole('button', { name: /clear all/i }).click();

    await page.locator('input[type="file"]').setInputFiles({
      name: 'browser-e2e.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n'),
    });
    await expect(page.getByText('browser-e2e.pdf')).toBeVisible();
    await page.getByRole('button', { name: /upload 1 file/i }).click();
    await expect(page.getByText('browser-e2e.pdf')).toBeVisible();

    await page.goto('/dashboard/settings');
    await page.locator('#current_password').fill('wrong-password');
    await page.locator('#new_password').fill('NewPassword123');
    await page.locator('#confirm_password').fill('NewPassword123');
    await page.getByRole('button', { name: /change password/i }).click();

    await expect(page.getByText(/current password is incorrect/i)).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard\/settings/);
  });

  test('runs the full study flow from upload through graded results', async ({ page }) => {
    test.setTimeout(90_000);

    await registerAndCreateCourse(page, `Browser Full Flow Biology ${Date.now()}`);

    await page.getByRole('button', { name: /upload files/i }).click();
    await page.locator('input[type="file"]').setInputFiles({
      name: 'full-flow-notes.pdf',
      mimeType: 'application/pdf',
      buffer: studyMaterial,
    });
    await page.getByRole('button', { name: /upload 1 file/i }).click();
    await expect(page.getByText('full-flow-notes.pdf')).toBeVisible();
    await expect(page.getByText('Ready')).toBeVisible({ timeout: 20_000 });

    await page.getByRole('button', { name: /ai analysis/i }).click();
    await page.getByRole('button', { name: /start ai analysis/i }).click();
    await expect(page.getByRole('heading', { name: /professor pattern analysis/i })).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole('button', { name: /^exams$/i }).click();
    await page.getByRole('button', { name: /generate exam/i }).click();
    await expect(page.getByRole('heading', { name: /generate practice exam/i })).toBeVisible();
    await page.getByPlaceholder('e.g. Midterm Practice').fill('Browser Full Flow Practice');
    await page.locator('input[type="range"]').evaluate((input) => {
      const range = input as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
      setter?.call(range, '5');
      range.dispatchEvent(new Event('input', { bubbles: true }));
      range.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await expect(page.getByText('5 questions')).toBeVisible();
    await page.getByRole('button', { name: /^generate exam$/i }).last().click();

    await expect(page).toHaveURL(/\/exam\//, { timeout: 30_000 });
    await expect(page.getByRole('heading', { name: 'Browser Full Flow Practice' })).toBeVisible();
    await expect(page.getByText('Q1 /')).toBeVisible();

    await answerEveryQuestion(page);
    await expect(page.getByText(/5 of 5 answered/i)).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /submit exam/i }).click();
    await page.getByRole('button', { name: /submit now/i }).click();

    await expect(page.getByText(/exam results/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/question breakdown/i)).toBeVisible();
    await expect(page.getByText(/AI grading tokens/i)).toBeVisible();

    await page.getByRole('button', { name: /back to course/i }).last().click();
    await page.getByRole('button', { name: /heatmap/i }).click();
    await expect(page.getByRole('heading', { name: /concept weakness heatmap/i })).toBeVisible();
    await expect(page.getByText(/no heatmap data yet/i)).not.toBeVisible();
  });
});
