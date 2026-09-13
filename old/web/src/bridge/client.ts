// Рантайм моста: один WebSocket, четыре типа сообщений, обещания на вызовы.
//
// Этот файл пишется руками - в отличие от api.ts, который печатает
// tools/gen_bridge.py. Здесь транспорт, там - список того, что можно звать.
//
// Адрес и токен приезжают в строке запроса: страницу открывает Python как
// /?t=<токен>&w=<порт сокета>. Другого способа их узнать у страницы нет -
// порт выбирает ОС при старте, а токен живёт один сеанс.

type Msg =
  | { t: "val"; path: string; v: unknown }
  | { t: "ret"; id: number; v?: unknown; e?: string }
  | { t: "sig"; name: string; a: unknown[] };

/** Сколько ждём ответа на call. План: 5 секунд. */
const TIMEOUT_MS = 5000;

const pending = new Map<
  number,
  { ok: (v: unknown) => void; bad: (e: Error) => void; timer: number }
>();
const settingWaiters = new Map<string, Array<(v: unknown) => void>>();
const signalHandlers = new Map<string, Set<(...a: unknown[]) => void>>();
/** Последнее известное значение настройки: мост шлёт val и без запроса. */
const cache = new Map<string, unknown>();

let seq = 0;
let sock: WebSocket | null = null;
/** Очередь на время, пока сокет ещё открывается. */
let outbox: string[] = [];

function params(): { token: string; wsPort: string } {
  const q = new URLSearchParams(location.search);
  return { token: q.get("t") ?? "", wsPort: q.get("w") ?? "" };
}

function send(obj: unknown): void {
  const raw = JSON.stringify(obj);
  if (sock && sock.readyState === WebSocket.OPEN) sock.send(raw);
  else outbox.push(raw);
}

function onMessage(raw: string): void {
  let m: Msg;
  try {
    m = JSON.parse(raw) as Msg;
  } catch {
    return; // мусор с нашего же сокета - молчим, ронять окно из-за него нельзя
  }

  if (m.t === "val") {
    cache.set(m.path, m.v);
    const waiting = settingWaiters.get(m.path);
    settingWaiters.delete(m.path);
    waiting?.forEach((fn) => fn(m.v));
    return;
  }

  if (m.t === "ret") {
    const p = pending.get(m.id);
    if (!p) return;
    pending.delete(m.id);
    clearTimeout(p.timer);
    // Жалоба вместо значения - это ответ, а не молчание. Без неё страница
    // не отличила бы «вернулось null» от «упало» и ждала бы таймаут зря.
    if (m.e) p.bad(new Error(m.e));
    else p.ok(m.v);
    return;
  }

  if (m.t === "sig") {
    signalHandlers.get(m.name)?.forEach((fn) => fn(...m.a));
  }
}

/** Поднять мост. Зовётся один раз при старте страницы. */
export function connect(): Promise<void> {
  const { token, wsPort } = params();
  if (!token || !wsPort) {
    // Витрина открывается без токена, и это нормально: моста там нет и не
    // нужно. Ронять её незачем - пусть просто живёт без Python.
    return Promise.reject(new Error("нет токена в адресе - страница открыта не из программы"));
  }
  return new Promise((ok, bad) => {
    const s = new WebSocket(`ws://127.0.0.1:${wsPort}/?t=${token}&w=${wsPort}`);
    sock = s;
    s.onmessage = (e) => onMessage(String(e.data));
    s.onopen = () => {
      outbox.forEach((raw) => s.send(raw));
      outbox = [];
      ok();
    };
    // 1008 - «нарушение правил», так мост закрывает сокет с чужим токеном.
    s.onclose = (e) => bad(new Error(`мост закрыт (${e.code})`));
  });
}

export function get(path: string): Promise<unknown> {
  return new Promise((ok) => {
    const list = settingWaiters.get(path) ?? [];
    list.push(ok);
    settingWaiters.set(path, list);
    send({ t: "get", path });
  });
}

export function set(path: string, v: unknown): void {
  cache.set(path, v);
  send({ t: "set", path, v });
}

/** Последнее известное значение без похода в Python. */
export function peek(path: string): unknown {
  return cache.get(path);
}

export function call(method: string, ...args: unknown[]): Promise<unknown> {
  const id = ++seq;
  return new Promise((ok, bad) => {
    const timer = window.setTimeout(() => {
      pending.delete(id);
      // Тот же текст, что показывает Backend._flush, когда запись не дошла:
      // человеку важно не «таймаут 5000 мс», а что настройка не сохранилась.
      bad(new Error("настройка не сохранилась"));
    }, TIMEOUT_MS);
    pending.set(id, { ok, bad, timer });
    send({ t: "call", m: method, a: args, id });
  });
}

export function onSignal(
  name: string,
  fn: (...a: unknown[]) => void,
): () => void {
  const set_ = signalHandlers.get(name) ?? new Set();
  set_.add(fn);
  signalHandlers.set(name, set_);
  return () => set_.delete(fn);
}
