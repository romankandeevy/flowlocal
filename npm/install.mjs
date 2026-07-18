#!/usr/bin/env node
/**
 * npx flowlocal - скачать свежий установщик FlowLocal и запустить его.
 *
 * Зачем это вообще существует. FlowLocal - программа на Python под Windows, и
 * в npm ей не место: там пакеты JavaScript. Но владельцу нужна установка одной
 * командой, и вот честный способ её дать: пакет не содержит программу, он
 * приносит её установщик из GitHub Releases. Ровно так поступают esbuild и
 * playwright - тянут свой бинарник, а не кладут его в реестр.
 *
 * Чего этот пакет НЕ делает и не будет: не ставит ничего молча, не просит прав
 * администратора, не лезет в реестр. Он скачивает подписанный вами же файл из
 * ваших же релизов и передаёт управление ему.
 *
 * Дальше человек живёт без npm вовсе: обновления приходят внутри приложения.
 */

import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pipeline } from "node:stream/promises";
import { createInterface } from "node:readline/promises";

const REPO = "romankandeevy/flowlocal";
const UA = { "User-Agent": "flowlocal-npm-installer" };

const c = {
  dim: (s) => `\x1b[2m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
  red: (s) => `\x1b[31m${s}\x1b[0m`,
};

function die(msg, hint) {
  console.error(`\n${c.red("Не вышло:")} ${msg}`);
  if (hint) console.error(c.dim(hint));
  process.exit(1);
}

if (process.platform !== "win32") {
  die(
    "FlowLocal пока только для Windows.",
    "macOS в планах - см. https://github.com/" + REPO + "#readme"
  );
}

console.log(`\n  ${c.bold("FlowLocal")} - диктовка, которая работает без интернета\n`);

// 1. Какая версия свежая
process.stdout.write("  спрашиваю GitHub… ");
let release;
try {
  const resp = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
    headers: UA,
  });
  if (!resp.ok) throw new Error(`ответ ${resp.status}`);
  release = await resp.json();
} catch (e) {
  die(`не удалось спросить GitHub (${e.message})`,
      "Проверьте интернет или скачайте вручную: " +
      `https://github.com/${REPO}/releases/latest`);
}

const asset = (release.assets || []).find((a) =>
  a.name.toLowerCase().endsWith("setup.exe")
);
if (!asset) die("в свежем релизе нет установщика");

const version = String(release.tag_name || "").replace(/^v/, "");
const mb = (asset.size / 1e6).toFixed(0);
console.log(`версия ${version}, ${mb} МБ\n`);

// 2. Спросить. Молча качать 70 МБ и запускать установщик - дурной тон.
if (!process.argv.includes("-y") && process.stdin.isTTY) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const answer = (await rl.question("  Скачать и установить? [Y/n] ")).trim().toLowerCase();
  rl.close();
  if (answer && !["y", "yes", "д", "да"].includes(answer)) {
    console.log(c.dim("\n  Хорошо. Файл всегда тут: " + release.html_url + "\n"));
    process.exit(0);
  }
}

// 3. Скачать с честным прогрессом
const dir = await mkdtemp(join(tmpdir(), "flowlocal-"));
const file = join(dir, asset.name);
process.stdout.write("\n  скачиваю   0%");
try {
  const resp = await fetch(asset.browser_download_url, { headers: UA, redirect: "follow" });
  if (!resp.ok || !resp.body) throw new Error(`ответ ${resp.status}`);
  const total = Number(resp.headers.get("content-length") || asset.size);
  let done = 0;
  let shown = -1;
  const ticker = new TransformStream({
    transform(chunk, controller) {
      done += chunk.byteLength;
      const pct = Math.floor((done / total) * 100);
      if (pct !== shown) {
        shown = pct;
        process.stdout.write(`\r  скачиваю ${String(pct).padStart(3)}%`);
      }
      controller.enqueue(chunk);
    },
  });
  await pipeline(resp.body.pipeThrough(ticker), createWriteStream(file));
  console.log("\r  скачано  100%\n");
} catch (e) {
  await rm(dir, { recursive: true, force: true });
  die(`скачивание оборвалось (${e.message})`,
      "Можно взять файл руками: " + release.html_url);
}

// 4. Отдать управление установщику. Прав администратора он не просит.
console.log(c.dim("  запускаю установщик - он не просит прав администратора\n"));
const child = spawn(file, [], { detached: true, stdio: "ignore", windowsHide: false });
child.unref();

console.log(`  Дальше следуйте окну установщика.`);
console.log(c.dim(`  После установки: нажмите Ctrl+Shift+Space в любом окне и говорите.`));
console.log(c.dim(`  Обновления приходят внутри программы - npm больше не понадобится.\n`));
