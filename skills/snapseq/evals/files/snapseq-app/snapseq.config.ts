import { defineConfig } from "snapseq";
import { label } from "snapseq-label";
import { pdf } from "snapseq-pdf";

// Both envs serve ./site in this fixture; a real staging env would have its own host.
const webServer = "pnpm dev";

export default defineConfig({
  envs: {
    dev: { host: "http://localhost:4173", webServer },
    staging: { host: "http://localhost:4173", webServer },
  },
  devices: {
    desktop: { viewport: { width: 1280, height: 800 } },
    mobile: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true },
  },
  plugins: [label(), pdf()],
});
