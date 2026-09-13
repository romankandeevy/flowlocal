// Переключатель на два-четыре взаимоисключающих значения: контейнер --fill,
// выбранный сегмент - бумага. Радиус контейнера 8, сегмента - на отступ
// меньше. Внутренний радиус ИМЕННО вычитанием, а не соседним токеном: при
// внешних 8 и отступе 3 стояло 6, то есть на единицу больше нужного, и дуги
// шли не эквидистантно. Глаз ловит это раньше, чем успевает понять, за что
// зацепился.
//
// Что досталось даром против QML. Там под клавиатуру написаны `step(delta)`,
// разбор Left/Right, обход по кругу, своя `mouseFocus` и FocusRing - и всё
// равно диктор не знал, что перед ним группа из трёх вариантов. Здесь это
// родные <input type="radio"> с общим `name`: браузер сам водит стрелками,
// сам заворачивает на краях, сам делает группу ОДНОЙ остановкой таба и сам
// говорит «переключатель, 2 из 4». Своего кода на это - ноль строк.
//
// Значение любого типа, в том числе булево (`{label: "включены", value: true}`
// стоит в настройках) и null. В DOM у радиокнопки значение только строкой,
// поэтому в атрибут кладём номер варианта, а наружу отдаём то, что лежало в
// options: иначе true и "true" стали бы одним и тем же.
import { useId } from "react";

import { cn } from "../cn";

export type SegmentedOption<T> = { label: string; value: T };

export function Segmented<T>({
  options,
  value,
  onChange,
  disabled = false,
  label,
  className,
}: {
  options: ReadonlyArray<SegmentedOption<T>>;
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  /** Имя группы для экранного диктора. */
  label?: string;
  className?: string;
}) {
  // Общий `name` и есть группа: по нему браузер связывает радиокнопки. useId
  // даёт своё имя каждой постановке - двух Segmented на странице бывает по
  // три, и с общим именем они переключали бы друг друга.
  const name = useId();

  const found = options.findIndex((o) => o.value === value);
  // Не нашли - первый, как в QML. Значение из конфига бывает старым: список
  // моделей меняется между версиями, и подсветить нечего.
  const index = found < 0 ? 0 : found;
  const count = options.length;

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "relative inline-grid h-[30px] rounded-md bg-fill p-[3px]",
        "transition-opacity duration-[var(--dur-fast)] ease-out",
        disabled && "opacity-40",
        className,
      )}
      // Колонки равной ширины, а не по длине подписи. В QML сегмент был шириной
      // с текст, и бегунок ездил по замерам соседей; в вебе такой замер стоил
      // бы ResizeObserver и пересчёта на каждой смене языка и подгрузке шрифта.
      // Равные колонки даёт сама сетка: 1fr под inline-grid растягивает все
      // колонки до самой широкой, контейнер при этом остаётся по содержимому.
      // Заодно исчезает анимация ширины бегунка - ездит только сдвиг.
      style={{ gridTemplateColumns: `repeat(${count}, minmax(36px, 1fr))` }}
    >
      {count > 0 ? (
        <span
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute top-[3px] bottom-[3px] left-[3px]",
            "rounded-[5px] border border-border bg-paper",
            "transition-transform duration-[var(--dur)] ease-out",
          )}
          // translateX в процентах считается от ширины самого бегунка, то есть
          // ровно от одной колонки: номер варианта переводится в сдвиг без
          // единого измерения DOM.
          style={{
            width: `calc((100% - 6px) / ${count})`,
            transform: `translateX(${index * 100}%)`,
          }}
        />
      ) : null}

      {options.map((option, i) => {
        const active = i === index;
        return (
          <label
            key={String(option.value)}
            className={cn(
              "group relative z-10 flex cursor-pointer items-center justify-center",
              "rounded-[5px] px-3 font-sans text-sm font-medium",
              "transition-colors duration-[var(--dur-fast)] ease-out",
              active
                ? "text-text"
                : // Ховер невыбранного - подложка на ступень выше. Одной подписи
                  // мало: на трёх сегментах непонятно, куда попадёт щелчок.
                  "text-text-muted hover:bg-fill-subtle hover:text-text-secondary",
              disabled && "cursor-default",
            )}
          >
            {/* Радиокнопка растянута на весь сегмент и обесцвечена, а не
                спрятана: кольцо фокуса рисуется по КОРОБКЕ элемента, который
                держит фокус, - значит, оно должно совпадать с сегментом. Со
                спрятанным полем кольцо ушло бы в точку, и его пришлось бы
                рисовать заново руками. */}
            <input
              type="radio"
              name={name}
              value={i}
              checked={active}
              disabled={disabled}
              onChange={() => onChange(option.value)}
              className={cn(
                "absolute inset-0 m-0 h-full w-full appearance-none rounded-[5px]",
                "bg-transparent",
                disabled ? "cursor-default" : "cursor-pointer",
              )}
            />
            {/* Нажатие: подпись чуть тонет. Бегунок в этот момент ещё едет к
                сегменту, и без отклика на самом сегменте первые 180 мс
                выглядят как «не нажалось». */}
            <span className="pointer-events-none transition-transform duration-[var(--dur-fast)] ease-out group-active:scale-[0.94]">
              {option.label}
            </span>
          </label>
        );
      })}
    </div>
  );
}
