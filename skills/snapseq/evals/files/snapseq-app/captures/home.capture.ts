import { capture, disableTransitions } from "snapseq";
import { openPage } from "./helpers/open-page";

capture(async ({ page, seq, device }) => {
  await disableTransitions(page);

  // Row 1: Home, top
  await openPage(page, "/");
  await seq.snap({ label: "Home" });

  // Row 2: Home, full
  await seq.snap({ fullPage: true, label: "Home" });

  // Row 3: Pricing, full
  await openPage(page, "/pricing");
  await seq.snap({ fullPage: true, label: "Pricing" });

  // Row 4: Docs, Contact link focused, full
  await openPage(page, "/docs");
  await page.getByRole("link", { name: "Contact" }).focus();
  await seq.snap({ fullPage: true, label: "Docs, Contact focused" });

  // Row 5: Home, menu open on mobile
  await openPage(page, "/");
  if (device === "mobile") {
    await page.getByRole("button", { name: "Menu" }).click();
  }
  await seq.snap({ label: "Home, menu" });
});
