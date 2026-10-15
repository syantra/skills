import type { Page } from "@playwright/test";

// Every capture opens pages through here, so a site quirk is handled once.
export async function openPage(page: Page, path: string) {
  await page.goto(path);
  await page.getByRole("heading", { level: 1 }).waitFor();
}
