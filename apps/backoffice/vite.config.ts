import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  plugins: [react()],
  // The KB design system lives at the repo root, outside this app.
  server: { fs: { allow: ["../.."] } },
});
