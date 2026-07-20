// Точка входа. Пока показывает витрину: своего окна у страницы ещё нет, мост
// пишется отдельно, а смотреть на контролы надо уже сейчас - иначе краски и
// отступы проверять нечем.
//
// Когда мост будет готов, здесь появится развилка: витрина по ?showcase, окно
// настроек по умолчанию. Разводить это раньше времени незачем.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app";
import { getSetting } from "./bridge/api";
import { connect } from "./bridge/client";
import { setLanguage } from "./i18n";
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

const root = document.getElementById("root");
if (!root) throw new Error("нет #root - index.html не тот");

function draw(what: React.ReactNode) {
  createRoot(root!).render(<StrictMode>{what}</StrictMode>);
}

if (new URLSearchParams(location.search).has("t")) {
  // Окно программы. Рисуем ПОСЛЕ того, как мост поднялся и язык прочитан:
  // иначе первый кадр уйдёт с пустыми настройками и русскими подписями, а
  // через долю секунды всё это моргнёт. Мост поднимается с 127.0.0.1, ждать
  // тут нечего.
  connect().then(
    async () => {
      window.__bridge = "ok";
      try {
        await setLanguage(String((await getSetting("ui_language")) || "ru"));
      } catch {
        // Язык не прочитался - остаёмся на русском. Окно важнее подписей.
      }
      draw(<App />);
    },
    (e: Error) => {
      window.__bridge = `нет: ${e.message}`;
      // Без моста окно бесполезно, но молчать нельзя: человек должен увидеть
      // причину, а не белый прямоугольник.
      draw(
        <div style={{ padding: 24, fontFamily: "sans-serif" }}>
          Не удалось связаться с программой: {e.message}
        </div>,
      );
    },
  );
} else {
  // Открыли в браузере руками - показываем витрину контролов. Моста здесь нет
  // и быть не должно.
  window.__bridge = "без моста";
  draw(<Showcase />);
}
