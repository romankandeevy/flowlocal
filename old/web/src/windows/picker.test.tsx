// Клавиатура пилюли выбора - половина задачи её переезда, и проверять её
// глазами нечем: окно живёт полсекунды и всплывает поверх чужого. Здесь
// проверяется то, что в QML держалось на Keys.onPressed и никем не мерялось:
// фокус приходит в список сам, цифры и стрелки доходят, Esc закрывает, а
// диктору список объявлен списком.
//
// Контраст и вид, как и на витрине, отсюда не видны - их меряют test_theme.py
// и глаза.
import axe from "axe-core";
import { act, fireEvent, render } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { Picker, type PickerItem } from "./picker";
import { Transcript } from "./transcript";

const ITEMS: PickerItem[] = [
  { id: "prompt", title: "Задание для ИИ", hint: "Сумбурная мысль - во внятную задачу" },
  { id: "shorter", title: "Короче", hint: "То же самое, но вдвое короче" },
  { id: "fix", title: "Только ошибки" },
];

/** Отрисовать пилюлю, дождавшись эффектов и кадра появления. */
async function draw(items: PickerItem[] = ITEMS) {
  const chosen = vi.fn();
  const cancelled = vi.fn();
  let out!: ReturnType<typeof render>;
  await act(async () => {
    out = render(
      <Picker
        items={items}
        preview="Ну вот, короче, я думаю, надо сделать"
        onChoose={chosen}
        onCancel={cancelled}
      />,
    );
    await new Promise((done) => requestAnimationFrame(() => done(null)));
  });
  return { ...out, chosen, cancelled };
}

/** Нажать клавишу там, где сейчас фокус. */
function press(key: string): void {
  const target = document.activeElement ?? document.body;
  act(() => {
    fireEvent.keyDown(target, { key });
  });
}

async function violations(node: Element): Promise<string[]> {
  const res = await axe.run(node, {
    resultTypes: ["violations"],
    rules: { "color-contrast": { enabled: false } },
  });
  return res.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}

test("фокус приходит в список сам, без единого щелчка", async () => {
  const { getByRole } = await draw();
  // Не «есть куда нажать», а именно «фокус уже там»: первое нажатие человека
  // уходит в никуда, если список его не забрал.
  expect(document.activeElement).toBe(getByRole("listbox"));
});

test("цифра выбирает пункт, а не соседний", async () => {
  const { chosen } = await draw();
  press("2");
  expect(chosen).toHaveBeenCalledWith("shorter");
});

test("стрелки листают обе оси и заворачиваются по кругу", async () => {
  const { getByRole } = await draw();
  const option = () => getByRole("option").textContent ?? "";

  press("ArrowRight");
  expect(option()).toContain("Короче");
  press("ArrowDown");
  expect(option()).toContain("Только ошибки");
  // С последнего вперёд - на первый: круг, а не тупик.
  press("ArrowDown");
  expect(option()).toContain("Задание для ИИ");
  // И назад с первого - на последний.
  press("ArrowUp");
  expect(option()).toContain("Только ошибки");
  press("ArrowLeft");
  expect(option()).toContain("Короче");
});

test("Enter применяет то, что показано, Esc закрывает", async () => {
  const { chosen, cancelled } = await draw();
  press("ArrowRight");
  press("Enter");
  expect(chosen).toHaveBeenCalledWith("shorter");
  expect(cancelled).not.toHaveBeenCalled();

  press("Escape");
  expect(cancelled).toHaveBeenCalledTimes(1);
});

test("диктор видит выбор, а не две строки текста", async () => {
  const { getByRole } = await draw();
  const list = getByRole("listbox");
  const option = getByRole("option");

  expect(option).toHaveAttribute("aria-selected", "true");
  // Место в списке - через posinset/setsize: в DOM лежит один пункт, а сказать
  // диктору надо «первый из трёх».
  expect(option).toHaveAttribute("aria-posinset", "1");
  expect(option).toHaveAttribute("aria-setsize", "3");
  expect(list).toHaveAttribute("aria-activedescendant", option.id);

  press("ArrowRight");
  // Ссылка обязана переехать на новый пункт: не переехала - диктор промолчит,
  // и человек не узнает, что список пролистался.
  expect(getByRole("listbox")).toHaveAttribute(
    "aria-activedescendant",
    getByRole("option").id,
  );
});

test("пустой список отвечает, а не молчит", async () => {
  const { queryByRole, getByRole, cancelled } = await draw([]);
  // Выбора нет - и списка нет: объявлять выбором то, где нечего выбрать,
  // значит обмануть диктора.
  expect(queryByRole("listbox")).toBeNull();
  expect(getByRole("status").textContent).toContain("нету");
  expect(document.activeElement).toBe(getByRole("status"));

  // Enter здесь закрывает: иначе окно, забравшее фокус, держало бы человека.
  press("Enter");
  expect(cancelled).toHaveBeenCalledTimes(1);
});

test("пилюля не нарушает доступность - и со списком, и без", async () => {
  const full = await draw();
  expect(await violations(full.container)).toEqual([]);
  full.unmount();

  const none = await draw([]);
  expect(await violations(none.container)).toEqual([]);
});

test("расшифровка: кнопки мертвы на пустом тексте, счёт слов честный", async () => {
  const save = vi.fn();
  const { getByRole, rerender, container } = render(
    <Transcript source="запись.ogg" text="" onSave={save} />,
  );
  expect(getByRole("button", { name: "Скопировать" })).toBeDisabled();
  expect(getByRole("button", { name: "Сохранить .txt" })).toBeDisabled();

  // Строка в фигурных скобках, а не в кавычках атрибута: JSX не разбирает в
  // них escape-последовательности, и «\n» приехал бы двумя знаками - перенос
  // строки как раз и проверяется.
  await act(async () => {
    rerender(
      <Transcript source="запись.ogg" text={"раз  два\nтри"} onSave={save} />,
    );
  });
  expect(container.textContent).toContain("3 слов");
  expect(getByRole("button", { name: "Сохранить .txt" })).toBeEnabled();

  act(() => {
    getByRole("button", { name: "Сохранить .txt" }).click();
  });
  expect(save).toHaveBeenCalledWith("раз  два\nтри");

  expect(await violations(container)).toEqual([]);
});
