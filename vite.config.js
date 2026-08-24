import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  // Relative asset URLs so the build also works from a sub-path, e.g. GitHub Pages.
  base: "./",
  build: {
    rollupOptions: {
      input: {
        player: fileURLToPath(new URL("index.html", import.meta.url)),
        raw10: fileURLToPath(new URL("raw10.html", import.meta.url)),
      },
    },
  },
});
