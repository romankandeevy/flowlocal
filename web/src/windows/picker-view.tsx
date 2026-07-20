// Окно списка преобразований: тонкая обёртка над Picker, которая ходит за
// данными в Python.
//
// Разделено надвое нарочно. `Picker` - это капсула и клавиатура, его можно
// показать на витрине и проверить тестом, не поднимая ни моста, ни Qt.
// Обёртка знает про мост и больше ни про что.
//
// **Фон здесь прозрачный, и это не украшение.** QML-окно пилюли создаётся
// прозрачным (`setColor(0,0,0,0)`), видно только саму капсулу. У страницы
// `body` красится в `--color-bg`, и без этой отмены поверх чужого окна
// всплывал бы непрозрачный прямоугольник во всю ширину вебвью.
import { useEffect, useState } from "react";

import { pickerItems } from "../bridge/api";
import { Picker, type PickerItem } from "./picker";

export function PickerView() {
  const [items, setItems] = useState<PickerItem[]>([]);

  useEffect(() => {
    // Список берём у Python: там он собирается из готовых (лежат кодом) и
    // своих (лежат в конфиге), да ещё с оглядкой на спрятанные. Второй
    // сборщик на странице разъехался бы с первым в первый же день, и выбор
    // молча уходил бы не туда.
    void pickerItems().then((v) => setItems((v as PickerItem[]) ?? []));

    const html = document.documentElement;
    const body = document.body;
    const before = [html.style.background, body.style.background];
    html.style.background = "transparent";
    body.style.background = "transparent";
    return () => {
      html.style.background = before[0] ?? "";
      body.style.background = before[1] ?? "";
    };
  }, []);

  return (
    <Picker
      items={items}
      preview=""
      onChoose={(id) => {
        // Применяет преобразование Python: у него на руках и выделенный
        // текст, и чужое окно, куда вставлять. Страница только называет
        // выбранное.
        //
        // ЭТОГО ВЫЗОВА ПОКА НЕТ в мосту, и выдумывать его здесь нельзя:
        // применение живёт в app.py, в конвейере вставки, а он в этой фазе
        // не трогается. Пока - в журнал, чтобы отказ был видимым, а не
        // молчаливым.
        console.warn("выбрано преобразование, применять пока нечем:", id);
      }}
      onCancel={() => window.close()}
    />
  );
}
