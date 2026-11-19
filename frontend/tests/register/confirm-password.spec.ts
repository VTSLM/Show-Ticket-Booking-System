import { test, expect, Locator } from '@playwright/test';

// #136: copy, cut, paste and drag-and-drop are blocked in Confirm Password only.

const registerUrl = '/auth/register';

// Fires a paste/copy/cut/drop event with text and returns whether the page blocked it.
async function fire(field: Locator, type: 'paste' | 'copy' | 'cut' | 'drop', text = 'Secret#123') {
  return field.evaluate(
    (el, { type, text }) => {
      const data = new DataTransfer();
      data.setData('text/plain', text);
      const event =
        type === 'drop'
          ? new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true })
          : new ClipboardEvent(type, { clipboardData: data, bubbles: true, cancelable: true });
      el.dispatchEvent(event);
      return event.defaultPrevented;
    },
    { type, text },
  );
}

test.describe('Register - confirm password', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(registerUrl);
  });

  for (const type of ['paste', 'copy', 'cut', 'drop'] as const) {
    test(`REG-CONFIRM-${type}: ${type} is blocked in Confirm Password`, async ({ page }) => {
      const confirm = page.locator('#confirmPassword');
      expect(await fire(confirm, type)).toBe(true);
      await expect(confirm).toHaveValue('');
      await expect(page.locator('#confirmPasswordHelp')).toHaveText('Please type your password again');
    });
  }

  test('REG-CONFIRM-password-field: paste still works in Password', async ({ page }) => {
    expect(await fire(page.locator('#password'), 'paste')).toBe(false);
  });

  test('REG-CONFIRM-typing: typing works and shows whether passwords match', async ({ page }) => {
    await page.locator('#password').fill('Secret#123');
    const confirm = page.locator('#confirmPassword');
    const help = page.locator('#confirmPasswordHelp');

    await confirm.pressSequentially('Secret#12');
    await expect(help).toHaveText("Passwords don't match");

    await confirm.pressSequentially('3');
    await expect(confirm).toHaveValue('Secret#123');
    await expect(help).toHaveText('Passwords match');
  });

  test('REG-CONFIRM-autofill: both fields keep autocomplete=new-password', async ({ page }) => {
    await expect(page.locator('#password')).toHaveAttribute('autocomplete', 'new-password');
    await expect(page.locator('#confirmPassword')).toHaveAttribute('autocomplete', 'new-password');
  });
});
