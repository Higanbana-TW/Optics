import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        player: fileURLToPath(new URL("index.html", import.meta.url)),
        raw10: fileURLToPath(new URL("raw10.html", import.meta.url)),
      },
    },
  },
});
