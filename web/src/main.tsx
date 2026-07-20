// Точка входа. Пока показывает витрину: своего окна у страницы ещё нет, мост
// пишется отдельно, а смотреть на контролы надо уже сейчас - иначе краски и
// отступы проверять нечем.
//
// Когда мост будет готов, здесь появится развилка: витрина по ?showcase, окно
// настроек по умолчанию. Разводить это раньше времени незачем.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { connect } from "./bridge/client";
import "./index.css";
import { Showcase } from "./ui/showcase";

// Мост поднимаем, только если страницу открыла программа: токен и порт сокета
// приезжают в адресе. В браузере на localhost:5173 их нет, и это не ошибка -
// витрину смотрят и без Python.
//
// Итог кладём в window: по нему проверяет tools/probe_webshell.py, что мост
// собрался в НАСТОЯЩЕМ вебвью, а не только в тесте. Без такой отметки проверять
// пришлось бы по виду страницы, то есть глазами.
declare global {
  interface Window {
    __bridge?: string;
  }
}

if (new URLSearchParams(location.search).has("t")) {
  connect().then(
    () => {
      window.__bridge = "ok";
    },
    (e: Error) => {
      window.__bridge = `нет: ${e.message}`;
    },
  );
} else {
  window.__bridge = "без моста";
}

const root = document.getElementById("root");
if (!root) throw new Error("нет #root - index.html не тот");

createRoot(root).render(
  <StrictMode>
    <Showcase />
  </StrictMode>,
);
