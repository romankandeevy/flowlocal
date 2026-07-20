// Таблица «слева -> справа» со строками, которые можно добавлять и убирать.
//
// Одна и та же машинерия нужна и подстановкам («моя почта» -> адрес), и
// правилам тона («outlook.exe» -> формально): разница только в подписях и в
// том, куда сохранять.
//
// ---- Настоящая <table>, а не столбик из строк ----
//
// В QML это Repeater из Row, и для того, кто слушает, там нет ни таблицы, ни
// столбцов: диктор читает подряд «поле ввода, поле ввода, кнопка Убрать» и
// сотню раз повторяет то же самое. Здесь разметка табличная, у столбцов есть
// <th>, и диктор называет столбец при переходе в ячейку. Заголовки при этом
// спрятаны от глаз (sr-only): что слева, а что справа, страница уже объяснила
// строкой над таблицей, и печатать это второй раз крупными буквами - лишнее
// слово, а не забота.
//
// Ширины столбцов заданы в <colgroup>, а не на <th>: спрятанные заголовки
// вынуты из потока, и table-fixed мерил бы по ним пустоту.
//
// ---- Два списка вместо одного ----
//
// Владелец сказал дословно: «там подстановки, и ты туда забил около полусотни
// просто системных, для программирования. Сделай это отдельным выездным
// пунктом, закрывающимся». Беда была не в том, что термины есть, а в том, что
// свои три подстановки лежали среди сотни чужих и терялись в них насмерть.
// Поэтому строк два списка: `rows` - свои, на виду; `ready` - те, что принесла
// программа, под раскрытием. Не удалены и не заперты: раскрыл - и правишь.
//
// ---- Почему одно onChange на оба списка ----
//
// Backend.setPairs собирает словарь ЗАНОВО из присланного. Отправь страница
// только свои строки - и сотня готовых терминов стёрлась бы от правки одной
// буквы в чужом поле. Раздельные обработчики позволяли бы написать ровно эту
// ошибку и не заметить её до первого гневного письма; один обработчик, который
// всегда несёт оба списка, её не позволяет.
import { useState } from "react";

import { Button } from "../button";
import { Card } from "../card";
import { cn } from "../cn";
import { Icon } from "../icons";

export interface Pair {
  /** Что говорю. Пустой ключ не сохраняется. */
  k: string;
  /** Что вставится. */
  v: string;
}

/**
 * Поле ввода внутри ячейки: высота 30, радиус 6, линия вместо заливки, фокус -
 * акцентная рамка.
 *
 * Кольца фокуса здесь нет намеренно, и это единственное исключение из общего
 * правила окна. У поля ввода о фокусе говорят курсор внутри и акцентная рамка,
 * третий признак того же события лишний. Кольцо к тому же зажигается только на
 * клавиатурный фокус, а в поле приходят и мышью, и табом одинаково часто.
 *
 * Живёт здесь, а не в общем наборе полей: таблицы переносились отдельной
 * веткой работы. Появится ui/form/input.tsx - заменить одной строкой.
 */
export function TableInput({
  value,
  label,
  placeholder,
  mono = false,
  onChange,
}: {
  value: string;
  /** Имя столбца. Заголовок <th> контролу именем не служит - ему нужно своё. */
  label: string;
  placeholder?: string;
  mono?: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      aria-label={label}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-[30px] w-full rounded-sm border border-border bg-fill-subtle px-3",
        "text-text placeholder:text-text-faint",
        "transition-[background-color,border-color]",
        "duration-[var(--dur-fast)] ease-out",
        "hover:border-border-strong hover:bg-fill",
        // Общее кольцо фокуса из index.css гасим ровно здесь - см. шапку.
        "focus:border-accent focus:bg-fill-subtle focus:outline-none",
        mono ? "font-mono text-2xs" : "font-sans text-sm",
      )}
    />
  );
}

/**
 * Одна строка таблицы: два поля, стрелка между ними, «Убрать».
 *
 * Про модель строка не знает ничего: наружу уходят только «поправили левое»,
 * «поправили правое» и «убрать», а какой список это записывает, решает
 * таблица. Иначе строке пришлось бы таскать с собой ссылку на свой список -
 * а списков два.
 */
export function PairRow({
  pair,
  leftLabel,
  rightLabel,
  leftPlaceholder,
  rightPlaceholder,
  onKeyEdited,
  onValueEdited,
  onRemoved,
}: {
  pair: Pair;
  leftLabel: string;
  rightLabel: string;
  leftPlaceholder?: string;
  rightPlaceholder?: string;
  onKeyEdited: (next: string) => void;
  onValueEdited: (next: string) => void;
  /**
   * Пусто - убирать нечего, и кнопки не будет. Так помечена строка-приглашение
   * пустой таблицы: убрать её нельзя, она и есть пустая таблица. В QML
   * приглашение лежало в модели, «Убрать» его убирало, и человек оставался
   * перед карточкой без единой строки - то самое «пусто, похожее на поломку»,
   * ради ухода от которого приглашение и завели.
   */
  onRemoved?: () => void;
}) {
  return (
    <tr>
      <td className="pr-2 pb-2">
        <TableInput
          value={pair.k}
          label={leftLabel}
          placeholder={leftPlaceholder}
          onChange={onKeyEdited}
        />
      </td>
      {/* Стрелка - рисунок, а не слово: смысл «слева меняется на правое» несут
          заголовки столбцов, и повторять его вслух незачем. */}
      <td
        aria-hidden="true"
        className="pr-2 pb-2 text-center font-sans text-md text-text-faint"
      >
        →
      </td>
      <td className="pr-2 pb-2">
        <TableInput
          value={pair.v}
          label={rightLabel}
          placeholder={rightPlaceholder}
          onChange={onValueEdited}
        />
      </td>
      <td className="pb-2">
        {/* Пять кнопок «Убрать» подряд на слух неразличимы, поэтому к подписи
            добавлена сама строка. Видно её только диктору: глазами строку и
            так видно - она в том же ряду. */}
        {onRemoved ? (
          <Button onClick={onRemoved} className="w-full">
            Убрать
            <span className="sr-only">: {pair.k || "пустая строка"}</span>
          </Button>
        ) : null}
      </td>
    </tr>
  );
}

/**
 * Сколько строк не сохранится. Об этом надо сказать вслух: иначе человек
 * напишет значение без ключа, закроет окно и потеряет его.
 *
 * В QML тут же вычиталась строка-приглашение: она лежала в модели, и
 * предупреждать «она не сохранится» про строку, которую человек не заводил,
 * значило ругать его за нашу же затею. Здесь приглашения в данных нет вовсе
 * (см. showBlankRow), и вычитать нечего.
 */
export function countBlanks(rows: Pair[]): number {
  return rows.filter((r) => r.k.trim() === "").length;
}

const EMPTY: Pair[] = [];

export function PairTable({
  rows,
  ready = EMPTY,
  onChange,
  leftHeader,
  rightHeader,
  caption,
  leftPlaceholder,
  rightPlaceholder,
  showBlankRow = false,
  readyTitle,
  readyHint,
}: {
  /** Свои строки. */
  rows: Pair[];
  /** Готовые, которые принесла программа. Пусто - раскрытия не будет вовсе. */
  ready?: Pair[];
  /** Всегда несёт оба списка - почему именно так, см. шапку файла. */
  onChange: (next: { rows: Pair[]; ready: Pair[] }) => void;
  /** Имя левого столбца: «Что говорю». */
  leftHeader: string;
  /** Имя правого столбца: «Что вставится». */
  rightHeader: string;
  /** Имя таблицы целиком - для того, кто её слушает, а не видит. */
  caption: string;
  leftPlaceholder?: string;
  rightPlaceholder?: string;
  /**
   * Показывать пустую строку, когда записей нет. Пустая таблица с одной серой
   * надписью не объясняет, что это вообще такое: человек видит сообщение, а не
   * форму. Живая строка с двумя полями и стрелкой между ними объясняет
   * устройство сама, без единого слова.
   *
   * Приглашение при этом остаётся ТОЛЬКО на экране: в `rows` его нет, пока
   * человек не начал печатать. В QML оно лежало в модели, и от этого пришлось
   * отдельно объяснять счётчику пустых строк, что первая - не в счёт.
   */
  showBlankRow?: boolean;
  /** Подпись свёрнутого пункта с готовыми. Задаёт страница: тексты окна живут
   *  на страницах, и заводить им второе место незачем. */
  readyTitle?: string;
  readyHint?: string;
}) {
  // Свёрнут ли пункт с готовыми. Состояние ведёт <details> сам, здесь мы его
  // лишь запоминаем, чтобы не создавать полтораста полей ввода, пока их не
  // видно: скрытая карточка стоила бы этих полей при каждом заходе на
  // страницу, заплаченных ни за что.
  const [readyOpen, setReadyOpen] = useState(false);

  // Приглашение показываем, но в данные не кладём: пока человек не напечатал
  // ни буквы, сохранять нечего.
  const invitation = rows.length === 0 && showBlankRow;
  const shown = invitation ? [{ k: "", v: "" }] : rows;

  function edit(list: Pair[], i: number, patch: Partial<Pair>): Pair[] {
    const next = list.map((r) => ({ ...r }));
    const cur = next[i];
    if (!cur) return list;
    next[i] = { ...cur, ...patch };
    return next;
  }

  const cols = (
    <colgroup>
      <col className="w-[190px]" />
      <col className="w-6" />
      <col />
      <col className="w-20" />
    </colgroup>
  );

  const head = (
    <thead>
      <tr>
        <th scope="col" className="sr-only">
          {leftHeader}
        </th>
        <th scope="col" className="sr-only">
          меняется на
        </th>
        <th scope="col" className="sr-only">
          {rightHeader}
        </th>
        <th scope="col" className="sr-only">
          Действие
        </th>
      </tr>
    </thead>
  );

  return (
    <Card>
      {shown.length > 0 ? (
        // Зазор между строками даёт нижний отступ ячеек, а не border-spacing:
        // тот добавил бы такой же зазор по краям таблицы, и его пришлось бы
        // вычитать из отступов карточки. Последняя строка платит те же 8 -
        // они и есть нижнее поле, поэтому снизу у обёртки только 6.
        <div className="px-6 pt-3.5 pb-1.5">
          <table className="w-full table-fixed">
            <caption className="sr-only">{caption}</caption>
            {cols}
            {head}
            <tbody>
              {shown.map((pair, i) => (
                <PairRow
                  // Индекс ключом - здесь это верно, а не лень: строки правят
                  // на месте, и ключ, собранный из содержимого, менялся бы на
                  // каждой набранной букве, то есть поле теряло бы фокус
                  // посреди слова.
                  key={i}
                  pair={pair}
                  leftLabel={leftHeader}
                  rightLabel={rightHeader}
                  leftPlaceholder={leftPlaceholder}
                  rightPlaceholder={rightPlaceholder}
                  onKeyEdited={(t) =>
                    onChange({ rows: edit(shown, i, { k: t }), ready })
                  }
                  onValueEdited={(t) =>
                    onChange({ rows: edit(shown, i, { v: t }), ready })
                  }
                  onRemoved={
                    invitation
                      ? undefined
                      : () =>
                          onChange({
                            rows: shown.filter((_, j) => j !== i),
                            ready,
                          })
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {/* ---- Готовые: свёрнутый пункт ----
          Появляется, только когда готовые строки есть: технические термины
          выключены - и таблица выглядит ровно как до этой правки.

          Раскрытие на <details>, как и «подробнее» в строке настройки. В QML
          под это написан ручной разбор Space и Enter, своё поле «мышиный ли
          фокус» и своё кольцо, и диктор всё равно не знает, что это
          раскрытие. Здесь он знает, а кода нет вовсе. */}
      {ready.length > 0 ? (
        <div>
          {/* Волосяная линия по краю содержимого, а не встык к рамке: у
              карточки скруглены углы, и линия во всю ширину упёрлась бы в
              дугу. Пункт - вторая часть таблицы, а не приклеенный к ней ящик. */}
          <div className="mx-6 h-px bg-border" />
          <details
            className="group"
            onToggle={(e) => setReadyOpen(e.currentTarget.open)}
          >
            <summary
              className={cn(
                "flex h-[52px] cursor-pointer list-none items-center gap-3",
                "mx-2 rounded-sm px-4",
                "transition-colors duration-[var(--dur-fast)] ease-out",
                "hover:bg-fill active:bg-fill-strong",
                "[&::-webkit-details-marker]:hidden",
              )}
            >
              {/* Шеврон в наборе смотрит вниз, поэтому свёрнутое состояние -
                  это поворот. Движется только он: под пунктом полтораста
                  полей, и прогонять их перекладку 180 мс подряд значит уронить
                  кадры на любом ноутбуке. */}
              <Icon
                name="chevron"
                size={16}
                strokeWidth={2.2}
                className={cn(
                  "shrink-0 -rotate-90 text-text-muted",
                  "transition-transform duration-[var(--dur)] ease-out",
                  "group-open:rotate-0",
                )}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-sans text-md text-text">
                  {readyTitle}
                </span>
                {readyHint ? (
                  <span className="block truncate font-sans text-sm text-text-muted">
                    {readyHint}
                  </span>
                ) : null}
              </span>
              {/* Сколько спрятано - числом, чтобы «пусто» и «свёрнуто» не
                  путались. */}
              <span className="shrink-0 font-mono text-sm text-text-faint">
                {ready.length}
              </span>
            </summary>

            <div className="px-6 pt-1.5 pb-1.5">
              {readyOpen ? (
                <table className="w-full table-fixed">
                  <caption className="sr-only">{readyTitle ?? caption}</caption>
                  {cols}
                  {head}
                  <tbody>
                    {ready.map((pair, i) => (
                      <PairRow
                        key={i}
                        pair={pair}
                        leftLabel={leftHeader}
                        rightLabel={rightHeader}
                        leftPlaceholder={leftPlaceholder}
                        rightPlaceholder={rightPlaceholder}
                        onKeyEdited={(t) =>
                          onChange({ rows, ready: edit(ready, i, { k: t }) })
                        }
                        onValueEdited={(t) =>
                          onChange({ rows, ready: edit(ready, i, { v: t }) })
                        }
                        onRemoved={() =>
                          onChange({
                            rows,
                            ready: ready.filter((_, j) => j !== i),
                          })
                        }
                      />
                    ))}
                  </tbody>
                </table>
              ) : null}
            </div>
          </details>
        </div>
      ) : null}
    </Card>
  );
}

// Пустого состояния у таблицы нет, и это решение, а не пропуск: показывает его
// страница, НАД таблицей.
//
// Объяснять надо до формы, а не под ней - ровно эту претензию владелец и
// высказал про подстановки. Решается оно один раз на заход: пустое состояние
// занимает вчетверо больше места, чем сменяющая его строка, и пересчитывай мы
// его на каждую правку - оно схлопывалось бы на первой же набранной букве, а
// поле уезжало бы вверх из-под курсора прямо во время ввода.
