// Критерий фазы 3, та его часть, которую можно проверить машиной.
//
// Что проверяется здесь: витрина собирается и рисуется целиком, обе темы
// живут на атрибуте <html data-theme>, axe-core не находит нарушений
// доступности, и по окну можно пройти табом.
//
// **Чего этот тест НЕ проверяет, и об этом надо знать.** Контраст красок axe
// в jsdom не считает и считать не может: правило color-contrast требует
// настоящей раскладки и настоящих вычисленных цветов, а в jsdom нет ни
// шрифтов, ни размеров. Оно отключается само, молча. Контраст у нас закрыт с
// другой стороны - test_theme.py меряет его по разобранному theme.css в обеих
// темах, по порогам WCAG. Ни один из двух тестов не заменяет другой.
//
// «Посмотреть глазами» тоже не заменяется: перепутанные местами иконки или
// слипшийся на 14 пикселях рисунок видны только человеку.
import axe from "axe-core";
import { act, render } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { Showcase } from "./showcase";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
});

/** Все нарушения axe в уже отрисованном узле, человеческим списком. */
async function violations(node: Element): Promise<string[]> {
  const res = await axe.run(node, {
    resultTypes: ["violations"],
    // Правила, которым нужна настоящая раскладка, в jsdom дают ложные ответы
    // в обе стороны. Выключаем явно, а не полагаемся на то, что axe сам
    // промолчит: молчание тут неотличимо от «проверено и чисто».
    rules: { "color-contrast": { enabled: false } },
  });
  return res.violations.map(
    (v) => `${v.id}: ${v.help} (${v.nodes.length})`,
  );
}

test("витрина рисуется и не нарушает доступность", async () => {
  const { container } = render(<Showcase />);
  expect(await violations(container)).toEqual([]);
});

test("тёмная тема ставится на <html>, а не на обёртку", async () => {
  const { container, getByRole } = render(<Showcase />);
  // Светлая по умолчанию - её ставит сама витрина при первой отрисовке.
  expect(document.documentElement.dataset["theme"]).toBe("light");

  // act, а не голый click: атрибут ставит useEffect, а он выполняется после
  // отрисовки. Без act проверка успевает раньше эффекта и читает старое
  // значение - тест падал именно так, и падал справедливо.
  await act(async () => {
    getByRole("button", { name: "Тёмная тема" }).click();
  });
  expect(document.documentElement.dataset["theme"]).toBe("dark");

  // Тёмную проверяем отдельно: часть нарушений доступности зависит от
  // состояния, а не от красок, и в другой теме дерево может быть другим.
  expect(await violations(container)).toEqual([]);
});

test("по витрине можно пройти табом", () => {
  const { container } = render(<Showcase />);
  // Всё, до чего доходит таб. Ничего не должно быть заперто в мышь: половина
  // задачи переезда - именно клавиатура, которой в QML-версии нет.
  const reachable = container.querySelectorAll(
    'button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])',
  );
  expect(reachable.length).toBeGreaterThan(0);

  // Отрицательный tabindex - это «мышью можно, клавиатурой нельзя». В своём
  // окне такого быть не должно ни у чего, что человек нажимает.
  const trapped = container.querySelectorAll('[tabindex="-1"]');
  expect(trapped.length).toBe(0);
});
