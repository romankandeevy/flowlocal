// Точка входа. Четыре окна из одного файла, плюс витрина.
//
// Что показать, говорит Python в адресе: `&v=settings|wizard|picker|transcript`.
// Собирать их в один интерфейс с переключателем было бы неправдой про то, как
// ими пользуются: мастер идёт один раз, picker всплывает поверх чужого окна и
// живёт секунды, настройки открывают раз в неделю.
//
// Открыли страницу руками в браузере - токена нет, и мы показываем витрину
// контролов. Это не запасной вариант на случай ошибки, а рабочий способ
// смотреть на вёрстку без Qt: `cd web && npm run dev`.
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app";
import { getSetting } from "./bridge/api";
import { connect } from "./bridge/client";
import { setLanguage } from "./i18n";
import "./index.css";
import { Wizard } from "./onboarding/wizard";
import { Showcase } from "./ui/showcase";

// Итог подъёма моста кладём в window: по нему проверяет
// tools/probe_webshell.py, что мост собрался в НАСТОЯЩЕМ вебвью, а не только
// в тесте. Без такой отметки проверять пришлось бы по виду страницы, то есть
// глазами.
declare global {
  interface Window {
    __bridge?: string;
  }
}

const root = document.getElementById("root");
if (!root) throw new Error("нет #root - index.html не тот");

function draw(what: ReactNode) {
  createRoot(root!).render(<StrictMode>{what}</StrictMode>);
}

function view(name: string): ReactNode {
  switch (name) {
    case "wizard":
      return <Wizard />;
    case "settings":
    default:
      return <App />;
  }
}

const params = new URLSearchParams(location.search);

if (params.has("t")) {
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
      draw(view(params.get("v") || "settings"));
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
  window.__bridge = "без моста";
  draw(<Showcase />);
}
