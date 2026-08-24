import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import { renameSync } from "node:fs";

function renameOfflineHtml() {
  return {
    name: "rename-offline-html",
    closeBundle() {
      renameSync("offline/index.html", "offline/RAW10-Lab-Offline.html");
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [viteSingleFile(), renameOfflineHtml()],
  build: {
    outDir: "offline",
    emptyOutDir: true,
  },
});
