// Точка входа. Пока показывает витрину: своего окна у страницы ещё нет, мост
// пишется отдельно, а смотреть на контролы надо уже сейчас - иначе краски и
// отступы проверять нечем.
//
// Когда мост будет готов, здесь появится развилка: витрина по ?showcase, окно
// настроек по умолчанию. Разводить это раньше времени незачем.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";
import { Showcase } from "./ui/showcase";

const root = document.getElementById("root");
if (!root) throw new Error("нет #root - index.html не тот");

createRoot(root).render(
  <StrictMode>
    <Showcase />
  </StrictMode>,
);
