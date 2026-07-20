// Расшифровка файла: сам текст и две кнопки - скопировать и сохранить .txt.
// Перенос qml/windows/Transcript.qml.
//
// Почему окно, а не вставка в активное поле. Диктовка целится туда, где
// человек сейчас стоит курсором, и это правильно: он сам туда встал секунду
// назад. С файлом наоборот - он перетащил его на окно программы, то есть стоит
// ЗДЕСЬ, а не в письме. Вставить час подкаста в случайное поле под курсором
// было бы не услугой, а происшествием.
//
// Поле для правки, а не просто надпись: расшифровку почти всегда правят перед
// тем, как куда-то деть, и делать это удобнее сразу. Поэтому «Скопировать» и
// «Сохранить» берут текст ИЗ ПОЛЯ, а не то, что приехало из Python.
//
// Окно ОДНО и переиспользуется: вторая расшифровка показывается в нём же.
// Отсюда сброс поля и подписи при смене text - иначе в новой расшифровке
// осталась бы правка от прошлой.
import { useEffect, useState } from "react";

import { copyText, on } from "../bridge/api";
import { t } from "../i18n";
import { Button } from "../ui/button";
import { Icon } from "../ui/icons";

export function Transcript({
  source = "",
  text,
  onSave,
}: {
  /** Имя исходного файла - шапкой: расшифровок за вечер бывает несколько, и
   *  без имени они неотличимы друг от друга. */
  source?: string;
  text: string;
  /**
   * Сохранить в .txt. Проп, а не вызов моста: диалог «куда сохранить» - это
   * QFileDialog на стороне Python (transcript_qt.save), и в api.ts метода под
   * него нет вовсе. Своего диалога у страницы быть не должно - браузерный
   * отдал бы файл в «Загрузки», а не рядом с исходником.
   */
  onSave: (text: string) => void;
}) {
  const [value, setValue] = useState(text);
  const [note, setNote] = useState("");

  useEffect(() => {
    setValue(text);
    setNote("");
  }, [text]);

  // Подпись рядом с кнопками приезжает сигналом flashed - тем же, которым
  // Backend отвечает на всё остальное (B.copyText шлёт «скопировано» сам).
  // В QML её ставил Python прямо в свойство окна; своего канала под одну
  // строку заводить незачем.
  //
  // Сама не гаснет, как и в QML: её сменит следующее действие или новая
  // расшифровка. Это подпись к сделанному, а не уведомление.
  useEffect(() => on("flashed", (flash) => setNote(String(flash))), []);

  // Слова считаем по тому же правилу, что в QML: пусто - не показываем ничего,
  // иначе «1 слово» стояло бы над пустым полем.
  const trimmed = value.trim();
  const words = trimmed ? trimmed.split(/\s+/).length : 0;

  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border px-5">
        <Icon name="file" size={20} className="shrink-0 text-text-secondary" />
        <div className="flex min-w-0 flex-col gap-0.5">
          <h1 className="truncate font-sans text-xl font-semibold text-text">
            {t("Расшифровка")}
          </h1>
          {/* В QML имя файла жуётся посередине, чтобы уцелело и начало, и
              расширение. В CSS такого многоточия нет, и подделывать его
              разворотом текста - хуже, чем отрезать хвост: развёрнутая строка
              ломается на скобках и точках. */}
          {source ? (
            <p className="truncate font-sans text-sm text-text-muted">{source}</p>
          ) : null}
        </div>
      </header>

      <div className="m-4 min-h-0 flex-1">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label={t("Расшифровка")}
          // resize-none: тянуть угол мышью в своём окне незачем, высоту задаёт
          // раскладка. Прокрутка своя, и браузер сам держит курсор в поле
          // зрения - в QML этого приходилось добиваться руками.
          className="h-full w-full resize-none bg-transparent font-sans text-md leading-[1.4] text-text"
        />
      </div>

      <div className="flex h-14 shrink-0 items-center gap-2 border-t border-border px-4">
        {/* ВЫЗОВ B.copyText(текст) - он же кладёт в буфер и шлёт flashed
            «скопировано», то есть заменяет обе половины QML-версии разом. */}
        <Button
          label={t("Скопировать")}
          kind="primary"
          disabled={words === 0}
          onClick={() => void copyText(value)}
        />
        <Button
          label={t("Сохранить .txt")}
          disabled={words === 0}
          onClick={() => onSave(value)}
        />
        {note ? (
          <p className="truncate font-sans text-sm text-text-muted">{note}</p>
        ) : null}

        {/* Сколько получилось - справа. Не украшение: по числу слов видно, что
            расшифровалась вся запись, а не первые полминуты. */}
        <span className="ml-auto shrink-0 font-mono text-2xs text-text-faint">
          {words > 0 ? `${words}${t(" слов")}` : ""}
        </span>
      </div>
    </div>
  );
}
