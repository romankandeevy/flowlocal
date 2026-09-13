// Сборка страниц настроек. Не Next.js: SSR, роутинг и серверные компоненты в
// локальном окне не нужны - мы грузимся с http://127.0.0.1 из своего же
// процесса, и сервер тут раздаёт папку, а не рендерит.
//
// base: "./" - пути в собранном index.html относительные. Иначе они уедут в
// корень сервера, а раздаём мы из web/dist по адресу с токеном в запросе.
// defineConfig берём у vitest, а не у vite: иначе блок `test` ниже не
// проходит проверку типов - в UserConfig у самого Vite такого поля нет.
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist",
    // Один файл вместо десятка: грузимся с localhost, где параллельные
    // запросы ничего не экономят, а лишние round-trip'ы к своему же QTcpServer
    // видны в задержке открытия окна. Она и так мимо порога - 443-475 мс при
    // 400 (замер фазы 0), и добивать её дроблением бандла незачем.
    cssCodeSplit: false,
    rollupOptions: { output: { manualChunks: undefined } },
    // Порог в плане - 120 КБ gzip. Предупреждение ставим туда же, чтобы
    // превышение было видно в выводе сборки, а не всплывало на выпуске.
    chunkSizeWarningLimit: 120,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
